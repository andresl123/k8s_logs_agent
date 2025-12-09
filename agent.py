import json
import os

import requests
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# --- CONFIGURATION ---
os.environ["GOOGLE_API_KEY"] = "dummy-key"


# --- TOOL 1: FETCH LOGS ---
def fetch_k8s_logs(search_query: str, lookback_minutes: int = 60) -> str:
    """
    Searches the Kubernetes logs (VictoriaLogs) for specific events.
    Args:
        search_query: The keyword to search for (e.g., 'error', 'checkout', 'crash').
        lookback_minutes: How many minutes back to search (default: 60).
    """

    url = "http://192.168.0.102:9428/select/logsql/query"
    full_query = f"{search_query} AND _time:{lookback_minutes}m"

    try:
        response = requests.get(url, params={"query": full_query})
        if response.status_code != 200:
            return f"Error: Database returned status {response.status_code}"

        logs = []
        for line in response.text.strip().split("\n"):
            if line:
                try:
                    d = json.loads(line)
                    # Try flat key first, then nested
                    pod = d.get("kubernetes.pod_name") or d.get("kubernetes", {}).get(
                        "pod_name", "unknown"
                    )
                    msg = d.get("_msg", "")
                    logs.append(f"[{d.get('_time')}] [{pod}] {msg}")
                except:
                    continue

        if not logs:
            return "No logs found matching that query."

        return "\n".join(logs[:50])

    except Exception as e:
        return f"Connection Failed: {e}"


# --- TOOL 2: REPORT FINDINGS (The Fix) ---
def report_findings(summary: str) -> str:
    """
    Use this tool to submit your final analysis to the user.
    """
    # We return a prompt injection that forces the model to stop looping.
    return "SYSTEM NOTICE: Analysis delivered. TASK COMPLETE. Do not call this tool again. Output the single word 'DONE' to finish."


# --- AGENT CONFIGURATION ---
local_model = LiteLlm(
    model="ollama/gemma3:12b", api_base="http://localhost:11434", temperature=0
)

root_agent = Agent(
    name="k8s_sre",
    model=local_model,
    tools=[fetch_k8s_logs, report_findings],
    instruction="""
    You are a Site Reliability Engineer (SRE).
    
    WORKFLOW:
    1. Call 'fetch_k8s_logs'.
    2. Analyze the logs.
    3. Call 'report_findings' with your summary.
    4. AFTER the tool returns, simply say "Analysis Complete" to finish.
    
    RULES:
    - Call 'report_findings' EXACTLY ONCE.
    - Do not loop.
    """,
)
