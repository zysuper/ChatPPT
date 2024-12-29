import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated
from langgraph.graph import add_messages
from typing_extensions import TypedDict
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import asyncio
from rich.console import Console
from rich.markdown import Markdown

model_name = "deepseek-chat"
openai_url = "https://api.deepseek.com"
openai_api_key = os.getenv("DEEPSEEK_API_KEY")
MAX_ROUND = 3

console = Console()

class State(TypedDict):
    messages: Annotated[list, add_messages]

def display(md: Markdown):
    console.print(md)

def writer_agent(writer_prompt, url=openai_url, api_key=openai_api_key):
    writer = writer_prompt | ChatOpenAI(
        model=model_name,
        max_tokens=8192,
        temperature=1.2,
        base_url=openai_url,
        api_key=openai_api_key,
    )
    return writer
    
def reflection_agent(reflection_prompt, url=openai_url, api_key=openai_api_key):
    reflect = reflection_prompt | ChatOpenAI(
        model=model_name,
        max_tokens=8192,
        temperature=0.2,
        base_url=openai_url,
        api_key=openai_api_key,
    ) 
    return reflect
    

def create_generation_node(writer_prompt, url=openai_url, api_key=openai_api_key):
    writer = writer_agent(writer_prompt, url, api_key)
    async def generation_node(state: State) -> State:
        write_task = state["messages"][0].content
        if len(state["messages"]) > 1:
            last_reflection = state["messages"][-1].content
            last_content = state["messages"][-2].content
        else:
            last_reflection = "No suggestions for improvement yet. This is the first writing attempt."
            last_content = "This is the first writing attempt. No previous content exists."
        return {"messages": [await writer.ainvoke({
            "write_task": write_task,
            "last_content": last_content,
            "last_reflection": last_reflection,
        })]}
    return generation_node

def create_reflection_node(reflection_prompt, url=openai_url, api_key=openai_api_key):
    reflect = reflection_agent(reflection_prompt, url, api_key)
    async def reflection_node(state: State) -> State:
        cls_map = {"ai": HumanMessage, "human": AIMessage}

        # 如果有多轮对话，则将前一轮的对话内容做 reflect 处理
        if len(state['messages']) > 1:
            translated = [state['messages'][0]] + [
                cls_map[msg.type](content=msg.content) for msg in state['messages'][1:]
            ]
        else:
            translated = [state['messages'][0]]
    
        res = await reflect.ainvoke(translated)

        return {"messages": [HumanMessage(content=res.content)]}
    return reflection_node

def should_continue(state: State):
    if len(state["messages"]) > MAX_ROUND:
        return END  # 达到条件时，流程结束
    return "reflect"  # 否则继续进入反思节点

def make_graph(writer_prompt, reflection_prompt, url=openai_url, api_key=openai_api_key):
    memory = MemorySaver()

    builder = StateGraph(State)
    generation_node = create_generation_node(writer_prompt, url, api_key)
    reflection_node = create_reflection_node(reflection_prompt, url, api_key)

    builder.add_node("writer", generation_node)
    builder.add_node("reflect", reflection_node)

    builder.add_edge(START, "writer")

    builder.add_conditional_edges(
        "writer",
        should_continue,
        {
            END: END,
            "reflect": "reflect",
        }
    )
    
    builder.add_edge("reflect", "writer")

    graph = builder.compile(checkpointer=memory)

    print(graph.get_graph().draw_ascii())

    return graph

def track_steps(func):
    step_counter = {'count': 0}  # 用于记录调用次数
    
    def wrapper(event, *args, **kwargs):
        # 增加调用次数
        step_counter['count'] += 1
        # 在函数调用之前打印 step
        display(Markdown(f"## Round {step_counter['count']}"))
        # 调用原始函数
        return func(event, *args, **kwargs)
    
    return wrapper

@track_steps
def pretty_print_event_markdown(event):
    # 如果是生成写作部分
    if 'writer' in event:
        generate_md = "#### 写作生成:\n"
        for message in event['writer']['messages']:
            generate_md += f"- {message.content}\n"
        display(Markdown(generate_md))
    
    # 如果是反思评论部分
    if 'reflect' in event:
        reflect_md = "#### 评论反思:\n"
        for message in event['reflect']['messages']:
            reflect_md += f"- {message.content}\n"
        display(Markdown(reflect_md))

async def main():
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "Reflection_PPTX"

    # 创建聊天提示模板，包括系统提示和消息占位符
    with open("./prompts/chatbot_agent.txt", "r", encoding="utf-8") as file:
        prompt = file.read().strip()
    writer_prompt = ChatPromptTemplate.from_messages([
            ("system", prompt),  # 系统提示部分
            (
                "human",
                "Please write content according to the following requirements: {write_task}"
            ),
            (
                "ai",
                "The previous content I wrote: {last_content}"
            ),
            (
                "human",
                "Here are the suggestions for improvement from the last review: {last_reflection}"
            ),
        ])
        
    reflection_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a professional content reviewer and reader, but not a writer. "
                " Your role is to provide detailed specific constructive critique and improvement suggestions from a reviewer's perspective."
                " For code: check correctness, readability and best practices."
                " For articles: evaluate structure, flow, and style."
                " For documents: assess completeness, logic, and organization."
                " Notice: Focus only on giving constructive feedback, do not write the content yourself!"
            ),
            MessagesPlaceholder(variable_name="messages"),  
            ]
        )
    graph = make_graph(writer_prompt, reflection_prompt)
    
    # async for event in graph.astream(
    #     {"messages": [HumanMessage(content="关于移民火星的未来规划。")]}, 
    #     {"configurable": {"session_id": "123", "thread_id": "123"}}):
    #     pretty_print_event_markdown(event)
    response = await graph.ainvoke(
        {"messages": [HumanMessage(content="关于移民火星的未来规划。")]}, 
        {"configurable": {"session_id": "123", "thread_id": "123"}}
    )
    print(response["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())