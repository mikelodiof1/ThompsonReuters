"""
    libraries definiton
"""
from fastapi import FastAPI, Request, Response, Cookie, HTTPException, Depends, WebSocket
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from typing import Optional, List
from fastapi.responses import HTMLResponse
from llm import prompt_llm, prompt_llm_async
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
import logging
import re


"""
    Start
"""
app = FastAPI()

"""
    fastappi code to avoid block cookies by browser in case of we use different domains

"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000/ai_chat"],  # replace with your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
    Define directory for html

"""
html_dir = Jinja2Templates(directory="html_files")


"""
    Cookie definition

"""
SECRET_KEY = "ThompsonReuters"
SESSION_COOKIE_NAME = "session_id"

"""
    Code to be unique a session
    :Source chatgpt

"""
serializer = URLSafeTimedSerializer(SECRET_KEY)


def get_session_id_from_cookie(session_id: Annotated[str | None, Cookie()] = None):
    """
        Function to validate cookie existence
        
        :param session_id: Cookie function to gather the value 
        :Source FastAPI doc
        :return: None | Error message
    """
    print(f"<<<<<Funcion get_session_id_from_cookie")
    if session_id is None:
        return None
    try:
        # Validate session ID
        session_data = serializer.loads(session_id, max_age=3600)  # Expires after 1 hour
        return session_data
    except Exception as e:
        # If the session ID is invalid or expired, raise an exception
        raise HTTPException(status_code=400, detail="Invalid session ID")

"""
    Main function, goal to display initial html page
"""  
@app.get("/ai_chat", response_class=HTMLResponse)
async def home(request: Request, session_data: dict = Depends(get_session_id_from_cookie)):
    """
        Main function, goal to display initial html page

        :param request and session_data 
        :Source FastAPI doc
        :return: html index page
    """  
    print("<<<<<<Funcion home")
    return html_dir.TemplateResponse("index.html", {"request": request, "session_data": session_data})


@app.get("/ai_chat/create-session", response_class=HTMLResponse)
async def create_session(request: Request, response: Response):
    """
        function, goal create new cookie with session details

        :param request and response 
        :Source chatGpt doc
        :return: html created_session page
    """  
    print("<<<<<<Function create session")
    # Generate a new session ID
    val_session_id = serializer.dumps({"user_id": 99999})  # Example session data
    
    # Set the session ID in the cookie
    try:
        logging.basicConfig(level=logging.DEBUG)
        # Before setting the cookie
        logging.debug("Setting cookie for the user.")
        response.set_cookie(key=SESSION_COOKIE_NAME, value=val_session_id, samesite="Lax", httponly=True, secure=False, path='/ai_chat', domain="localhost:8000/ai_chat")
        # After setting the cookie
        logging.debug("Cookie set in response: %s", response.headers.get('Set-Cookie'))
    except Exception as e:
        print(f"Error setting cookie: {e}")
    return html_dir.TemplateResponse("session_created.html", {"request": request})

@app.get("/ai_chat/get-cookie")
async def get_cookie(request: Request, session_id: str = Cookie(None)):
    """
        function, goal read a cookie

        :param request and session_id 
        :Source FastAPI doc
        :return: html index page
    """  
    print(f"<<<<<<<Function Get cookie")
    if session_id:
        return HTMLResponse(content=f"Cookie value: {session_id}")
    else:
        return HTMLResponse(content="No cookie found.")
    

@app.get("/ai_chat/delete-session", response_class=HTMLResponse)
async def delete_session(request: Request, response: Response):
    """
        function, goal delete a cookie

        :param request and session_id 
        :Source FastAPI doc
        :return: html index page
    """  
    response.delete_cookie(SESSION_COOKIE_NAME)
    return html_dir.TemplateResponse("session_deleted.html", {"request": request})

"""
        class functions, goal manage websocket connections

        :param request and session_id 
        :Source ChatGPT doc
        :return: html index page
"""  
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

"""
  Dictionary list to store user message history
"""  
chat_hist=[]

@app.get("/ai_chat/history/")
async def get_chat_history():
    return chat_hist

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
        function, on each event, sent the message to LLM app

        :param websocket 
        :Source ChatGPT doc
        :return: Display a message in a list
    """  
    await manager.connect(websocket)
    
    """
        Welcome message

    """  
    ai_Msg=''
    
    usr_Msg="Hey hi!"
    stream=prompt_llm(user_message_content="Hey hello")
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            ai_Msg += chunk.choices[0].delta.content
    
    await websocket.send_text("Welcome to AI assistant")
    await websocket.send_text(ai_Msg)
    
    new_message = {
        "role": "user",
        "content": usr_Msg
    } 
    chat_hist.append(new_message)
    
    new_message = {
        "role": "assistant",
        "content": ai_Msg
    }
    
    chat_hist.append(new_message)
    
    try:
        while True:
            data = await websocket.receive_text()
            """
               Chat dialogue between user and LLM

            """  
            await manager.broadcast(f"Client says: {data}")
                                   
            new_message = {
               "role": "user",
               "content": data
            } 
            
            chat_hist.append(new_message)
            
            """
               Change ai prompt engine

            """  
            pattern = r'\bai\b'    
            matches = re.findall(pattern, data, re.IGNORECASE)    
            if len(matches) > 0:                
                chat_hist.clear()
                new_message = {
                 "role": "user",
                 "content": "Hi, introduce your self, please"
                } 
                chat_hist.append(new_message)   
            
            
            """
               Chat dialogue between user and LLM

            """                         
            ai_Msg=""
            stream = await prompt_llm_async(user_message_content=data, existing_messages=chat_hist)
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    ai_Msg += chunk.choices[0].delta.content
            await websocket.send_text(f"AI Assistant: {ai_Msg}")
                      
            new_message = {
              "role": "assistant",
              "content": ai_Msg
            }    
            chat_hist.append(new_message)
            
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(websocket)
