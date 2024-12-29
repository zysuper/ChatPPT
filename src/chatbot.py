# chatbot.py

import os
from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # 导入提示模板相关类
from langchain_core.messages import HumanMessage  # 导入消息类
from langchain_core.runnables.history import RunnableWithMessageHistory  # 导入带有消息历史的可运行类

from logger import LOG  # 导入日志工具
from chat_history import get_session_history
from writer_and_reflect_agent import make_graph


class ChatBot(ABC):
    """
    聊天机器人基类，提供聊天功能。
    """
    def __init__(self, prompt_file="./prompts/chatbot.txt", session_id=None):
        self.prompt_file = prompt_file
        self.session_id = session_id if session_id else "default_session_id"
        self.prompt = self.load_prompt()
        # LOG.debug(f"[ChatBot Prompt]{self.prompt}")
        self.create_chatbot()

    def load_prompt(self):
        """
        从文件加载系统提示语。
        """
        try:
            with open(self.prompt_file, "r", encoding="utf-8") as file:
                return file.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到提示文件 {self.prompt_file}!")


    def create_chatbot(self):
        """
        初始化聊天机器人，包括系统提示和消息历史记录。
        """
        # 创建聊天提示模板，包括系统提示和消息占位符
        writer_prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompt),  # 系统提示部分
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

        # 创建一个 runnable 将输入转换为 graph 需要的格式
        def input_transformer(input_messages):
            if isinstance(input_messages, list) and len(input_messages) > 0:
                # 获取第一条消息的内容作为写作任务
                write_task = input_messages[0].content
                return {"messages": [HumanMessage(content=write_task)]}
            return {"messages": []}
        
        def output_transformer(output_messages):
            if isinstance(output_messages, dict) and "messages" in output_messages:
                return output_messages["messages"][-1]
            return output_messages

        # 创建 graph 并将其包装为 runnable
        graph = make_graph(writer_prompt, reflection_prompt)

        # 将 input_transformer 和 output_transformer 应用到 graph 上
        self.chatbot = input_transformer | graph | output_transformer

        # 将聊天机器人与消息历史记录关联
        self.chatbot_with_history = RunnableWithMessageHistory(self.chatbot, get_session_history)


    async def chat_with_history(self, user_input, session_id=None):
        """
        处理用户输入，生成包含聊天历史的回复。

        参数:
            user_input (str): 用户输入的消息
            session_id (str, optional): 会话的唯一标识符

        返回:
            str: AI 生成的回复
        """
        if session_id is None:
            session_id = self.session_id
    
        response = await self.chatbot_with_history.ainvoke(
            [HumanMessage(content=user_input)],
            {"configurable": {"session_id": session_id, "thread_id": session_id}},  # 传入配置，包括会话ID
        )

        LOG.debug(f"[ChatBot] {response.content}")  # 记录调试日志
        return response.content  # 返回生成的回复内容