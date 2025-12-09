import smtplib
import os
import re # Added for fallback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import markdown, use fallback if missing
try:
    import markdown
except ImportError:
    markdown = None

# Load environment variables
load_dotenv()

def send_report_email(to_email: str, subject: str, summary_md: str, cover_card: dict = None, ticker: str = "", date_str: str = None) -> dict:
    """
    Send the Daily Digest report via email.
    
    Args:
        to_email (str): Recipient email address.
        subject (str): Email subject.
        summary_md (str): The markdown content of the summary.
        cover_card (dict, optional): Data for the cover card (sentiment, score, etc.).
        ticker (str, optional): The ticker symbol.
        date_str (str, optional): The date of the report. Defaults to current date if None.
        
    Returns:
        dict: {"success": bool, "message": str}
    """
    # 1. Get SMTP Configuration
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if not sender_email or not sender_password:
        return {
            "success": False, 
            "message": "SMTP credentials (SMTP_EMAIL, SMTP_PASSWORD) are not set in .env"
        }
        
    try:
        # 2. Convert Markdown to HTML
        # Pre-process markdown to fix common LLM formatting issues
        # 1. Clean up potential residual code blocks at the very end (just in case)
        summary_md = re.sub(r'```\s*$', '', summary_md.strip())
        
        # 2. Fix inline lists: "Text * Item" -> "Text\n\n* Item"
        # Aggressive fix: ANY space-asterisk-space sequence becomes a newline-bullet
        # We replace " * " with "\n\n* "
        summary_md = summary_md.replace(" * ", "\n\n* ")
        
        # Also handle cases where there might be a colon immediately before the asterisk without space
        # e.g. "Topic:* Item"
        summary_md = re.sub(r'([：:])\s*\*\s*', r'\1\n\n* ', summary_md)
        
        # Ensure we didn't break bold formatting like "**Bold**" (which became "* *Bold**")
        # If we accidentally created "* *", revert it back to " **" (space bold)
        summary_md = summary_md.replace("\n\n* *", " **")
        
        # Fix specific pattern seen in user screenshot: "关键话题： * WBD"
        # The previous replace(" * ") handles the spaces, but let's ensure predecessors
        pass
        
        if markdown:
            html_content = markdown.markdown(summary_md, extensions=['tables', 'fenced_code'])
        else:
            logger.warning("Markdown library not found. Using simple fallback for email HTML.")
            # Simple Fallback:
            # 1. Escape HTML (minimal) - assuming input is safe or we trust content
            html_content = summary_md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # 2. Headers
            html_content = re.sub(r'^### (.*)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'^## (.*)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'^# (.*)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
            # 3. Bold
            html_content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_content)
            # 4. Newlines to <br> or <p>
            lines = html_content.split('\n')
            html_content = ""
            for line in lines:
                if line.strip().startswith("<h"):
                    html_content += line
                else:
                    html_content += f"<p>{line}</p>"
        
        # 3. Create HTML Body
        full_html = _create_email_html(html_content, cover_card, ticker, date_str)
        
        # 4. Create Message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        
        # Add plain text version (optional but good practice)
        text_part = MIMEText(summary_md, "plain")
        msg.attach(text_part)
        
        # Add HTML version
        html_part = MIMEText(full_html, "html")
        msg.attach(html_part)
        
        # 5. Send Email
        logger.info(f"Sending email to {to_email} via {smtp_server}:{smtp_port}")
        
        try:
            # Choose valid connection method based on port
            if smtp_port == 465:
                # Implicit SSL
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                # STARTTLS (Explicit SSL)
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.starttls() # Secure the connection
            
            with server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_email, msg.as_string())
            
            logger.info("Email sent successfully.")
            return {"success": True, "message": "Email sent successfully!"}
            
        except smtplib.SMTPConnectError:
            return {"success": False, "message": f"Could not connect to {smtp_server}:{smtp_port}. Check network or firewall."}
        except smtplib.SMTPAuthenticationError:
            return {"success": False, "message": "Authentication failed. Check your email and password (or App Password)."}
        except OSError as e:
             # Handle "Network is unreachable" and other socket errors
            return {"success": False, "message": f"Network error: {str(e)}. Try changing port to 465 in .env if using 587."}
            
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"success": False, "message": f"Failed to send email: {str(e)}"}

def _create_email_html(content_html: str, card: dict, ticker: str, date_str: str = None) -> str:
    """Helper to construct the full HTML email."""
    
    # Default values
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        # Ensure it's just the date part (defensive)
        date_str = str(date_str).split(' ')[0]
    
    ticker = ticker or card.get('ticker', 'N/A') if card else 'Report'
    
    # Card Logic
    card_html = ""
    if card:
        score = float(card.get('sentiment_score', 5))
        if score >= 6:
            badge_color = "#10b981" # Green
            badge_bg = "rgba(16, 185, 129, 0.1)"
        elif score <= 4:
            badge_color = "#ef4444" # Red
            badge_bg = "rgba(239, 68, 68, 0.1)"
        else:
            badge_color = "#f59e0b" # Amber
            badge_bg = "rgba(245, 158, 11, 0.1)"
            
        headline = card.get('headline', 'Market Insight')
        sentiment_label = card.get('sentiment_label', 'N/A')
        factors = card.get('key_factors', [])
        factors_html = "".join([
            f'<span style="display:inline-block; background:rgba(30,41,59,0.8); color:#e2e8f0; padding:4px 10px; border-radius:10px; font-size:12px; margin:2px; border:1px solid #475569;">{f}</span>' 
            for f in factors
        ])
        
        # Inline styles for email compatibility (tables are safest)
        card_html = f"""
        <!-- Cover Card -->
        <div style="background: linear-gradient(145deg, #1e293b, #0f172a); border-radius: 16px; padding: 30px; margin-bottom: 30px; color: white; text-align: center; max-width: 400px; margin-left: auto; margin-right: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="font-size: 36px; font-weight: 900; letter-spacing: 2px; margin-bottom: 5px;">{ticker}</div>
            <div style="font-size: 13px; color: #94a3b8; margin-bottom: 20px;">{date_str}</div>
            
            <div style="display: inline-block; padding: 8px 20px; border-radius: 20px; font-size: 16px; font-weight: 700; color: {badge_color}; background-color: {badge_bg}; border: 2px solid {badge_color}; margin-bottom: 10px;">
                {sentiment_label}
            </div>
            
            <div style="font-size: 14px; color: #e2e8f0; margin-bottom: 20px;">
                Score: {score:.1f}/10
            </div>
            
            <div style="font-size: 20px; font-weight: 700; line-height: 1.4; color: #f8fafc; margin-bottom: 20px;">
                {headline}
            </div>
            
            <div style="margin-bottom: 20px;">
                {factors_html}
            </div>
            
            <div style="font-size: 10px; color: #64748b; letter-spacing: 2px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                WGD INSIGHT DATA
            </div>
        </div>
        """
    
    # Full Template
    template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1, h2, h3 {{ color: #1e293b; }}
            a {{ color: #2563eb; text-decoration: none; }}
            code {{ background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-family: monospace; }}
            pre {{ background: #f1f5f9; padding: 15px; border-radius: 8px; overflow-x: auto; }}
            blockquote {{ border-left: 4px solid #cbd5e1; margin: 0; padding-left: 15px; color: #64748b; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px; }}
        </style>
    </head>
    <body>
        {card_html}
        
        <div style="background: white; padding: 20px; border-radius: 8px;">
            {content_html}
        </div>
        
        <div class="footer">
            <p>Generated by WGD Insight Daily Digest</p>
            <p>来自拗拗</p>
        </div>
    </body>
    </html>
    """
    return template
