import gradio as gr
import os
from loguru import logger
from main import generate_pptx_from_markdown

# 读取系统提示词
def load_system_prompt():
    try:
        with open('prompts/formatter.txt', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取系统提示词失败: {e}")
        return "系统提示词加载失败"

SYSTEM_PROMPT = load_system_prompt()

def process_and_generate(message, history):
    output_file_path = generate_pptx_from_markdown(message)
    history.append((message, f"PPTX 生成成功,文件路径: {output_file_path}"))
    return history, "", output_file_path

def clear_chatbot(chatbot):
    return [],None

# 创建Gradio界面
with gr.Blocks() as demo:
    with gr.Row():  
        with gr.Column(scale=1):
            gr.Markdown("# ChatPPT助手")
            gr.Markdown("## 系统提示词")
            gr.Markdown(SYSTEM_PROMPT, label="系统提示词")
            pptx_output = gr.File(label="PPTX文件")
        with gr.Column(scale=2):
            chatbot = gr.Chatbot()
            with gr.Row():
                submit_btn = gr.Button("生成PPTX", interactive=False)
                clear_btn = gr.Button("清除")
            msg = gr.Textbox(label="输入你的PPT需求")

            clear_btn.click(
                fn=clear_chatbot,  # 清除聊天记录的函数
                inputs=[],  # 输入参数
                outputs=[chatbot, pptx_output]  # 输出参数
            )
            msg.change(
                fn=lambda x: gr.update(interactive=bool(x)), 
                inputs=[msg],
                outputs=[submit_btn]
            )
            submit_btn.click(
                fn=process_and_generate,  # 处理用户输入的函数
                inputs=[msg, chatbot],  # 输入参数
                outputs=[chatbot, msg, pptx_output]  # 输出参数
            )


if __name__ == "__main__":
    demo.launch()
