from dotenv import load_dotenv
import asyncio
import aiosmtplib
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
# import smtplib
from email.message import EmailMessage


load_dotenv(override=True)

# def push(text):
#     requests.post(
#         "https://api.pushover.net/1/messages.json",
#         data={
#             "token": os.getenv("PUSHOVER_TOKEN"),
#             "user": os.getenv("PUSHOVER_USER"),
#             "message": text,
#         }
#     )

async def sendEmail(text, subject="New website message"):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = 587 # int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM") or smtp_user
    email_to = os.getenv("EMAIL_TO") or os.getenv("OWNER_EMAIL") or email_from
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ["1", "true", "yes"]
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ["1", "true", "yes"]

    if not smtp_host or not email_from or not email_to:
        print(f"[email] Missing SMTP config. Would have emailed: '{text}' to {email_to or 'UNKNOWN'}")
        return {"emailed": "skipped", "reason": "missing_config"}

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = email_to
    message["Subject"] = subject
    message.set_content(str(text))

    print(f"[email] Sending email to {email_to} with subject {subject}")

    # if use_ssl:
    #     with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
    #         if smtp_user and smtp_pass:
    #             server.login(smtp_user, smtp_pass)
    #         server.send_message(message)
    # else:
    #     with smtplib.SMTP(smtp_host, smtp_port) as server:
    #         server.ehlo()
    #         if use_tls:
    #             server.starttls()
    #             server.ehlo()
    #         if smtp_user and smtp_pass:
    #             server.login(smtp_user, smtp_pass)
    #         server.send_message(message)
    # return {"emailed": "ok"}

    try:
        if use_ssl:
            async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=True) as server:
                if smtp_user and smtp_pass:
                    await server.login(smtp_user, smtp_pass)
                asyncio.run(server.send_message(message))
        else:
            async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=use_tls) as server:
                if smtp_user and smtp_pass:
                    await server.login(smtp_user, smtp_pass)
                asyncio.run(server.send_message(message))
        return {"emailed": "ok"}
    except Exception as e:
        print(f"[email] Failed to send email: {e}")
        return {"emailed": "error", "error": str(e)}

def record_user_details(email, name="Name not provided", notes="not provided"):
    print("+++ in record_user_details")
    sendEmail(f"The following user info was collected...\n\nName: {name}\nEmail: {email}\nNotes: {notes}", "[LinkedIn Agent] New user details")
    return {"recorded": "ok"}

def record_unknown_question(question):
    print("+++ in record_unknown_question")
    sendEmail(f"The following question was asked:\n\n{question}", "[LinkedIn Agent] Unknown question")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class Me:

    def __init__(self):
        # self.openai = OpenAI()
        # self.model = "gpt-4o-mini"
        self.openai = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")
        self.model = "deepseek-chat"
        self.name = "Jordan Phillips"
        reader = PdfReader("linkedin.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model=self.model, messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    me = Me()
    gr.ChatInterface(me.chat, type="messages").launch()
    