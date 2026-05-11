from IPython.display import display, Image, clear_output, HTML

def render_terminal_ui(task, step, max_steps, agent_state, action_str, action_result, screenshot_bytes):
    """
    Me-render UI gaya terminal/Command Prompt di Google Colab.
    Kini mendukung tampilan Memory, Plan, Reflection, dan Thought.
    """
    clear_output(wait=True)

    reflection = agent_state.get("reflection", "")
    plan = agent_state.get("plan", "")
    memory = agent_state.get("memory", "")
    thought = agent_state.get("thought", "")

    html = f"""
    <div style="font-family: 'Courier New', Courier, monospace; background-color: #0d1117; color: #c9d1d9; padding: 15px; border-radius: 5px; max-width: 900px; margin: 0 auto; box-shadow: 0 4px 8px rgba(0,0,0,0.5);">
        <div style="border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 15px;">
            <strong style="color: #58a6ff;">[ROOT@AI-BROWSER]</strong> ~ TASK: <span style="color: #fff; font-weight: bold;">{task}</span>
            <span style="float: right; color: #8b949e;">(Step {step}/{max_steps})</span>
        </div>

        <div style="display: flex; gap: 15px; margin-bottom: 15px;">
            <div style="flex: 1; border: 1px solid #30363d; padding: 10px; border-radius: 4px; background-color: #161b22;">
                <div style="color: #d2a8ff; font-weight: bold; margin-bottom: 5px; border-bottom: 1px dashed #30363d;">📝 PLAN (TO-DO)</div>
                <div style="font-size: 13px;">{plan}</div>
            </div>
            <div style="flex: 1; border: 1px solid #30363d; padding: 10px; border-radius: 4px; background-color: #161b22;">
                <div style="color: #3fb950; font-weight: bold; margin-bottom: 5px; border-bottom: 1px dashed #30363d;">🧠 MEMORY (NOTES)</div>
                <div style="font-size: 13px;">{memory}</div>
            </div>
        </div>

        <div style="background-color: #161b22; padding: 10px; border-left: 3px solid #ff7b72; margin-bottom: 10px;">
            <span style="color: #ff7b72; font-weight: bold;">[REFLECTION]</span> : {reflection}
        </div>

        <div style="background-color: #161b22; padding: 10px; border-left: 3px solid #79c0ff; margin-bottom: 10px;">
            <span style="color: #79c0ff; font-weight: bold;">[THOUGHT]</span> : {thought}
        </div>

        <div style="background-color: #161b22; padding: 10px; border-left: 3px solid #a5d6ff; margin-bottom: 10px;">
            <span style="color: #a5d6ff; font-weight: bold;">[ACTION]</span> : {action_str}
        </div>

        <div style="background-color: #161b22; padding: 10px; border-left: 3px solid #3fb950; margin-bottom: 15px;">
            <span style="color: #3fb950; font-weight: bold;">[RESULT]</span> : {action_result}
        </div>

        <div style="border-top: 1px dashed #30363d; padding-top: 10px;">
            <span style="color: #8b949e; font-size: 12px; font-weight: bold;">-- Current Browser View --</span><br/>
    """
    display(HTML(html))

    if screenshot_bytes:
        display(Image(data=screenshot_bytes, width=900))

    display(HTML("</div></div>"))
