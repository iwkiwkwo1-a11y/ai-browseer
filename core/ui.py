from IPython.display import display, Image, clear_output, HTML
import time

def render_terminal_ui(task, step, max_steps, thought, action_str, action_result, screenshot_bytes):
    """
    Me-render UI gaya terminal/Command Prompt di Google Colab.
    Lebih ringan, tidak mencolok, dan fokus pada teks + gambar.
    """
    clear_output(wait=True)

    html = f"""
    <div style="font-family: 'Courier New', Courier, monospace; background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px; max-width: 900px; margin: 0 auto; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
        <div style="border-bottom: 1px dashed #555; padding-bottom: 10px; margin-bottom: 10px;">
            <strong style="color: #4CAF50;">[ROOT@AI-BROWSER]</strong> ~ TASK: <span style="color: #fff;">{task}</span>
            <span style="float: right; color: #888;">(Step {step}/{max_steps})</span>
        </div>

        <div style="margin-bottom: 8px;">
            <span style="color: #569cd6;">> [THINKING]</span> : {thought}
        </div>

        <div style="margin-bottom: 8px;">
            <span style="color: #ce9178;">> [ACTION]</span>   : {action_str}
        </div>

        <div style="margin-bottom: 15px;">
            <span style="color: #b5cea8;">> [RESULT]</span>   : {action_result}
        </div>

        <div style="border-top: 1px dashed #555; padding-top: 10px;">
            <span style="color: #888; font-size: 12px;">-- Current Browser View --</span><br/>
    """
    display(HTML(html))

    if screenshot_bytes:
        display(Image(data=screenshot_bytes, width=900))

    display(HTML("</div></div>"))
