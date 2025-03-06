import streamlit as st
import time
import random
import base64
from datetime import datetime, timedelta
import os
from PIL import Image
import io

# Set page configuration
st.set_page_config(
    page_title="WhatsApp Clone",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to make it look like WhatsApp
st.markdown("""
<style>
    /* Main background color */
    .main {
        background-color: #f0f2f5;
    }
    
    /* Chat container */
    .chat-container {
        background-color: #e5ddd5;
        background-image: url("https://web.whatsapp.com/img/bg-chat-tile-light_a4be512e7195b6b733d9110b408f075d.png");
        border-radius: 10px;
        padding: 10px;
        height: 70vh;
        overflow-y: auto;
    }
    
    /* Message bubbles */
    .message-bubble-sent {
        background-color: #d9fdd3;
        border-radius: 7.5px;
        padding: 6px 7px 8px 9px;
        margin: 5px 0;
        max-width: 65%;
        float: right;
        clear: both;
        position: relative;
        box-shadow: 0 1px 0.5px rgba(0, 0, 0, 0.13);
    }
    
    .message-bubble-received {
        background-color: #ffffff;
        border-radius: 7.5px;
        padding: 6px 7px 8px 9px;
        margin: 5px 0;
        max-width: 65%;
        float: left;
        clear: both;
        position: relative;
        box-shadow: 0 1px 0.5px rgba(0, 0, 0, 0.13);
    }
    
    /* Message time */
    .message-time {
        font-size: 11px;
        color: rgba(0, 0, 0, 0.45);
        float: right;
        margin-left: 10px;
        margin-top: 2px;
    }
    
    /* Header */
    .chat-header {
        background-color: #f0f2f5;
        padding: 10px;
        border-radius: 10px 10px 0 0;
        display: flex;
        align-items: center;
    }
    
    .chat-header img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        margin-right: 10px;
    }
    
    .chat-header-info {
        flex-grow: 1;
    }
    
    .chat-header-name {
        font-weight: bold;
        margin: 0;
    }
    
    .chat-header-status {
        font-size: 12px;
        color: #667781;
        margin: 0;
    }
    
    /* Input area */
    .input-area {
        background-color: #f0f2f5;
        padding: 10px;
        border-radius: 0 0 10px 10px;
        display: flex;
        align-items: center;
    }
    
    /* Sidebar */
    .sidebar {
        background-color: #ffffff;
        border-right: 1px solid #e9edef;
        height: 100vh;
    }
    
    /* Contact list */
    .contact {
        display: flex;
        align-items: center;
        padding: 10px;
        border-bottom: 1px solid #f0f2f5;
        cursor: pointer;
    }
    
    .contact:hover {
        background-color: #f5f6f6;
    }
    
    .contact img {
        width: 49px;
        height: 49px;
        border-radius: 50%;
        margin-right: 15px;
    }
    
    .contact-info {
        flex-grow: 1;
    }
    
    .contact-name {
        font-weight: 500;
        margin: 0;
    }
    
    .contact-message {
        font-size: 13px;
        color: #667781;
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .contact-time {
        font-size: 12px;
        color: #667781;
    }
    
    /* Double check mark */
    .double-check {
        color: #53bdeb;
        font-size: 14px;
        margin-right: 5px;
    }
    
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: transparent; 
    }
    
    ::-webkit-scrollbar-thumb {
        background: #888; 
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #555; 
    }
    
    /* Emoji picker */
    .emoji-picker {
        position: absolute;
        bottom: 60px;
        right: 20px;
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        padding: 10px;
        z-index: 1000;
    }
    
    /* Image in message */
    .message-image {
        max-width: 100%;
        border-radius: 5px;
        margin-bottom: 5px;
    }
    
    /* Attachment button */
    .attachment-button {
        cursor: pointer;
        color: #8696a0;
        margin-right: 10px;
    }
    
    /* Voice message */
    .voice-message {
        display: flex;
        align-items: center;
        padding: 5px 0;
    }
    
    .voice-message-icon {
        color: #8696a0;
        margin-right: 10px;
    }
    
    .voice-message-waveform {
        flex-grow: 1;
        height: 20px;
        background-color: rgba(0, 0, 0, 0.1);
        border-radius: 10px;
    }
    
    .voice-message-duration {
        margin-left: 10px;
        font-size: 12px;
        color: rgba(0, 0, 0, 0.45);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = {
        'João': [
            {'text': 'Oi, tudo bem?', 'time': '09:30', 'sender': 'João', 'read': True},
            {'text': 'Vamos almoçar hoje?', 'time': '09:31', 'sender': 'João', 'read': True},
        ],
        'Maria': [
            {'text': 'Bom dia! Você viu o e-mail que te enviei?', 'time': '08:45', 'sender': 'Maria', 'read': True},
        ],
        'Grupo Família': [
            {'text': 'Alguém vai no aniversário da tia no domingo?', 'time': '10:15', 'sender': 'Pedro', 'read': True},
            {'text': 'Eu vou!', 'time': '10:20', 'sender': 'Ana', 'read': True},
            {'text': 'Também vou, levo o bolo', 'time': '10:25', 'sender': 'você', 'read': True},
        ],
        'Carlos': [
            {'text': 'E aí, como foi a reunião?', 'time': 'ontem', 'sender': 'Carlos', 'read': True},
        ],
        'Ana': [],
        'Pedro': [
            {'text': 'Você tem o contato daquele cliente?', 'time': '12:05', 'sender': 'Pedro', 'read': True},
        ],
    }

if 'current_chat' not in st.session_state:
    st.session_state.current_chat = 'João'

if 'online_status' not in st.session_state:
    st.session_state.online_status = {
        'João': 'online',
        'Maria': 'last seen today at 10:30',
        'Carlos': 'last seen yesterday at 23:15',
        'Ana': 'typing...',
        'Pedro': 'online',
        'Grupo Família': '5 participants',
    }

if 'unread_count' not in st.session_state:
    st.session_state.unread_count = {
        'João': 0,
        'Maria': 2,
        'Carlos': 1,
        'Ana': 0,
        'Pedro': 0,
        'Grupo Família': 3,
    }

if 'profile_pics' not in st.session_state:
    # Generate random colors for profile pics
    st.session_state.profile_pics = {}
    for contact in ['João', 'Maria', 'Carlos', 'Ana', 'Pedro', 'Grupo Família']:
        color = f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"
        st.session_state.profile_pics[contact] = color

if 'show_emoji_picker' not in st.session_state:
    st.session_state.show_emoji_picker = False

if 'show_attachment_menu' not in st.session_state:
    st.session_state.show_attachment_menu = False

# Function to get profile picture
def get_profile_pic(contact):
    color = st.session_state.profile_pics[contact]
    return f"""
    <div style="width:49px;height:49px;border-radius:50%;background-color:{color};
                display:flex;justify-content:center;align-items:center;color:white;font-weight:bold;">
        {contact[0]}
    </div>
    """

# Function to format message time
def format_message_time(time_str):
    if time_str in ['ontem', 'yesterday']:
        return time_str
    else:
        return time_str

# Function to convert image to base64
def get_image_base64(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

# Layout with two columns: contacts and chat
col1, col2 = st.columns([1, 3])

# Contacts column
with col1:
    st.markdown('<div style="padding:10px;background-color:#f0f2f5;"><h3>WhatsApp Clone</h3></div>', unsafe_allow_html=True)
    
    # Search bar
    st.text_input("", placeholder="Search or start new chat", key="search_contacts")
    
    # Contact list
    for contact in st.session_state.messages.keys():
        # Get last message and time
        last_message = "Click to start chatting"
        last_time = ""
        if st.session_state.messages[contact]:
            last_msg = st.session_state.messages[contact][-1]
            if 'image' in last_msg:
                last_message = "📷 Photo"
            elif 'voice' in last_msg:
                last_message = "🎤 Voice message"
            else:
                last_message = last_msg['text']
            
            last_time = last_msg['time']
            if len(last_message) > 30:
                last_message = last_message[:27] + "..."
        
        # Create contact element
        contact_html = f"""
        <div class="contact" onclick="this.style.backgroundColor='#ebebeb'">
            {get_profile_pic(contact)}
            <div class="contact-info">
                <h4 class="contact-name">{contact}</h4>
                <p class="contact-message">
                    {"✓✓ " if st.session_state.messages[contact] and st.session_state.messages[contact][-1]['sender'] == 'você' else ""}
                    {last_message}
                </p>
            </div>
            <div>
                <div class="contact-time">{last_time}</div>
                {f'<div style="background-color:#25D366;color:white;border-radius:50%;width:20px;height:20px;text-align:center;line-height:20px;margin-top:5px;">{st.session_state.unread_count[contact]}</div>' if st.session_state.unread_count[contact] > 0 else ''}
            </div>
        </div>
        """
        
        # Make the contact clickable
        if st.markdown(contact_html, unsafe_allow_html=True):
            st.session_state.current_chat = contact
            st.session_state.unread_count[contact] = 0

# Chat column
with col2:
    # Chat header
    current_chat = st.session_state.current_chat
    header_html = f"""
    <div class="chat-header">
        {get_profile_pic(current_chat)}
        <div class="chat-header-info">
            <h4 class="chat-header-name">{current_chat}</h4>
            <p class="chat-header-status">{st.session_state.online_status[current_chat]}</p>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
    
    # Chat container
    chat_container = st.container()
    
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # Display messages
        for msg in st.session_state.messages[current_chat]:
            is_sent = msg['sender'] == 'você'
            bubble_class = "message-bubble-sent" if is_sent else "message-bubble-received"
            
            message_html = f"""
            <div class="{bubble_class}">
                {f'<strong>{msg["sender"]}</strong><br>' if not is_sent and current_chat == 'Grupo Família' else ''}
            """
            
            # Check if message contains an image
            if 'image' in msg:
                message_html += f"""
                <img src="data:image/jpeg;base64,{msg['image']}" class="message-image">
                """
            
            # Check if message contains a voice message
            elif 'voice' in msg:
                message_html += f"""
                <div class="voice-message">
                    <span class="voice-message-icon">🎤</span>
                    <div class="voice-message-waveform"></div>
                    <span class="voice-message-duration">{msg['voice']}</span>
                </div>
                """
            
            # Regular text message
            if 'text' in msg and msg['text']:
                message_html += f"{msg['text']}"
            
            message_html += f"""
                <span class="message-time">
                    {msg['time']} {' ✓✓' if is_sent and msg['read'] else ''}
                </span>
            </div>
            <div style="clear:both"></div>
            """
            st.markdown(message_html, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Input area
    st.markdown('<div class="input-area">', unsafe_allow_html=True)
    
    # Emoji button, attachment button, message input, and send button
    col_emoji, col_attach, col_input, col_send = st.columns([1, 1, 10, 1])
    
    with col_emoji:
        if st.button("😊"):
            st.session_state.show_emoji_picker = not st.session_state.show_emoji_picker
    
    with col_attach:
        if st.button("📎"):
            st.session_state.show_attachment_menu = not st.session_state.show_attachment_menu
    
    with col_input:
        message_input = st.text_input("", placeholder="Type a message", key="message_input")
    
    with col_send:
        send_button = st.button("📤")
    
    # Emoji picker
    if st.session_state.show_emoji_picker:
        emoji_col1, emoji_col2, emoji_col3 = st.columns([1, 1, 1])
        with emoji_col1:
            if st.button("😀"):
                if 'message_input' in st.session_state:
                    st.session_state.message_input += "😀"
        with emoji_col2:
            if st.button("❤️"):
                if 'message_input' in st.session_state:
                    st.session_state.message_input += "❤️"
        with emoji_col3:
            if st.button("👍"):
                if 'message_input' in st.session_state:
                    st.session_state.message_input += "👍"
    
    # Attachment menu
    if st.session_state.show_attachment_menu:
        attachment_col1, attachment_col2, attachment_col3 = st.columns([1, 1, 1])
        with attachment_col1:
            st.markdown("📷 Photo")
            uploaded_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"], key="image_upload")
            if uploaded_file is not None:
                # Process the uploaded image
                image_bytes = uploaded_file.read()
                image_base64 = get_image_base64(image_bytes)
                
                # Add image message to chat
                current_time = datetime.now().strftime("%H:%M")
                new_message = {
                    'image': image_base64,
                    'text': '',
                    'time': current_time,
                    'sender': 'você',
                    'read': False
                }
                st.session_state.messages[current_chat].append(new_message)
                
                # Hide attachment menu
                st.session_state.show_attachment_menu = False
                
                # Rerun to update UI
                st.rerun()
        
        with attachment_col2:
            st.markdown("🎤 Voice")
            if st.button("Record Voice"):
                # Simulate voice recording
                current_time = datetime.now().strftime("%H:%M")
                new_message = {
                    'voice': '0:12',
                    'text': '',
                    'time': current_time,
                    'sender': 'você',
                    'read': False
                }
                st.session_state.messages[current_chat].append(new_message)
                
                # Hide attachment menu
                st.session_state.show_attachment_menu = False
                
                # Rerun to update UI
                st.rerun()
        
        with attachment_col3:
            st.markdown("📄 Document")
            if st.button("Select Document"):
                # Simulate document upload
                current_time = datetime.now().strftime("%H:%M")
                new_message = {
                    'text': '📄 Document.pdf',
                    'time': current_time,
                    'sender': 'você',
                    'read': False
                }
                st.session_state.messages[current_chat].append(new_message)
                
                # Hide attachment menu
                st.session_state.show_attachment_menu = False
                
                # Rerun to update UI
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Handle sending message
    if send_button and message_input:
        # Add message to chat
        current_time = datetime.now().strftime("%H:%M")
        new_message = {
            'text': message_input,
            'time': current_time,
            'sender': 'você',
            'read': False
        }
        st.session_state.messages[current_chat].append(new_message)
        
        # Clear input
        st.session_state.message_input = ""
        
        # Simulate reply after 1-3 seconds for some contacts
        if current_chat in ['João', 'Ana', 'Maria'] and random.random() > 0.5:
            # Set typing status
            st.session_state.online_status[current_chat] = 'typing...'
            
            # Prepare automated responses
            responses = {
                'João': ['Ok, combinado!', 'Que horas?', 'Vamos sim!', 'Tudo bem e você?'],
                'Ana': ['Entendi', 'Que legal!', 'Vou ver isso', 'Me manda mais detalhes'],
                'Maria': ['Obrigada pela informação', 'Já vi o documento', 'Podemos conversar mais tarde?', 'Perfeito!']
            }
            
            # Add reply after a short delay
            time.sleep(random.uniform(1, 2))
            reply = {
                'text': random.choice(responses[current_chat]),
                'time': datetime.now().strftime("%H:%M"),
                'sender': current_chat,
                'read': True
            }
            st.session_state.messages[current_chat].append(reply)
            
            # Reset status
            st.session_state.online_status[current_chat] = 'online'
        
        # Rerun to update UI
        st.rerun()

# Add some features in the sidebar
with st.sidebar:
    st.markdown("### WhatsApp Web")
    st.markdown("Keep your phone connected")
    st.markdown("WhatsApp connects to your phone to sync messages.")
    
    # Profile settings
    st.markdown("---")
    st.markdown("### Profile")
    st.text_input("Your Name", value="User", key="profile_name")
    st.text_area("Status", value="Available", key="profile_status")
    
    # Theme toggle
    st.markdown("---")
    st.markdown("### Settings")
    theme = st.selectbox("Theme", ["Light", "Dark"])
    notifications = st.checkbox("Enable Notifications", value=True)
    
    # About
    st.markdown("---")
    st.markdown("### About")
    st.markdown("This is a WhatsApp clone created with Streamlit.")
    st.markdown("© 2023 WhatsApp Clone") 
