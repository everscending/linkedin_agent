from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, OpenAIChatCompletionsModel 
import os
from pypdf import PdfReader
import gradio as gr
import mailtrap as mt

load_dotenv(override=True)

def mailtrapSendEmail(text, subject="New website message"):

    email = os.getenv("EMAIL_FROM")
    client = mt.MailtrapClient(token=os.getenv("MAILTRAP_API_KEY"))

    # Create mail object
    mail = mt.Mail(
        sender=mt.Address(email="hello@demomailtrap.co"),
        to=[mt.Address(email=email)],
        subject=subject,
        text=text,
    )

    client.send(mail)


@function_tool
def record_user_details(email, name="Name not provided", notes="not provided"):
    """Use this tool to record that a user is interested in being in touch and provided an email address
    
    Args:
        email (str): The email address of this user
        name: (str, optional): The user's name, if they provided it
        notes: (str, optional): Any additional information about the conversation that's worth recording to give context
    """
    print(f"record_user_details...\n\nName: {name}\nEmail: {email}\nNotes: {notes}", flush=True)
    mailtrapSendEmail(f"The following user info was collected...\n\nName: {name}\nEmail: {email}\nNotes: {notes}", "[LinkedIn Agent] New user details")
    return {"recorded": "ok"}

@function_tool
def record_unknown_question(question):
    """Use this tool to record any question that couldn't be answered as you didn't know the answer

    Args:
        question (str): The question that couldn't be answered
    """
    print(f"record_unknown_question...\n\nQuestion: {question}", flush=True)
    mailtrapSendEmail(f"The following question was asked:\n\n{question}", "[LinkedIn Agent] Unknown question")
    return {"recorded": "ok"}

tools = [record_user_details, record_unknown_question]

class Me:

    def __init__(self):
        self.name = "Jordan Phillips"
        reader = PdfReader("linkedin.pdf")

        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()

        # DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
        # deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        # deepseek_client = AsyncOpenAI(base_url=DEEPSEEK_BASE_URL, api_key=deepseek_api_key)
        # model = OpenAIChatCompletionsModel(model="deepseek-chat", openai_client=deepseek_client)

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_client = AsyncOpenAI(api_key=openai_api_key)
        model = OpenAIChatCompletionsModel(model="gpt-4o-mini", openai_client=openai_client)

        agent = Agent(
            name="DigitalTwin", 
            instructions=self.system_prompt(), 
            model=model, 
            tools=tools,
        )

        self.agent = agent
    
    def system_prompt(self) -> str:
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. "
        system_prompt += "If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career."
        system_prompt += "If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool."

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."

        print ('system_prompt...', system_prompt, flush=True)
        return system_prompt
    
    async def chat(self, message) -> str:

        result = await Runner.run(self.agent, message)
        return result.final_output

if __name__ == "__main__":
    me = Me()
    gr.ChatInterface(me.chat, type="messages").launch()
    