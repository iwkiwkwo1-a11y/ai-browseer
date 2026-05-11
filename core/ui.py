from IPython.display import display, Image, clear_output, HTML

def render_terminal_ui(task, step, max_steps, agent_state, action_str, action_result, screenshot_bytes):
    """
    Me-render UI gaya terminal/Command Prompt di Google Colab.
    Kini mendukung tampilan Memory, Plan, Reflection, dan Thought.
    """
    clear_output(wait=True)

    reflection = agent_state.get("reflection", "")
    plan = agent_state.get("plan", "")
    memory_obj = agent_state.get("memory", {})
    thought = agent_state.get("thought", "")

    # Format Structured Memory ke HTML
    mem_html = ""
    if isinstance(memory_obj, dict):
        facts = memory_obj.get("facts", [])
        fails = memory_obj.get("failed_paths", [])
        notes = memory_obj.get("notes", "")

        mem_html += "<strong>Facts:</strong><ul style='margin-top:2px; margin-bottom:5px; padding-left:15px;'>"
        for f in facts: mem_html += f"<li>{f}</li>"
        mem_html += "</ul>"

        if fails:
            mem_html += "<strong style='color:#ff7b72;'>Failed Paths:</strong><ul style='margin-top:2px; margin-bottom:5px; padding-left:15px;'>"
            for f in fails: mem_html += f"<li>{f}</li>"
            mem_html += "</ul>"

        mem_html += f"<strong>Notes:</strong> {notes}"
    else:
        mem_html = str(memory_obj)

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
                <div style="color: #3fb950; font-weight: bold; margin-bottom: 5px; border-bottom: 1px dashed #30363d;">🧠 STRUCTURED MEMORY</div>
                <div style="font-size: 13px;">{mem_html}</div>
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
