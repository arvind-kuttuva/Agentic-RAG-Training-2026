from src.api.v1.agents.agents import run_search_agent, run_search_agent_stream
from src.api.v1.core.guardrails import guard_input, guard_output


# def query_documents(query: str):
   

#    result = run_search_agent(query)

def query_documents_old(query: str):
   #Input guardrais: toxicity+topic restriction (may raise GuardrailViolation)
   guard_input(query)

   result = run_search_agent(query)
   if isinstance(result, dict) and result.get("answer"):      
      result = guard_output(result["answer"])

   # return run_search_agent(query)
   return result
   # return run_search_agent(query)


def query_documents(query: str):
   #Input guardrais: toxicity+topic restriction (may raise GuardrailViolation)
   guard_input(query)

   result = run_search_agent(query)
   if isinstance(result, dict):
      answer = result.get("answer", "")
      if answer:
         result["answer"] = guard_output(answer)

   # return run_search_agent(query)
      return result
   return guard_output(result)
   # return run_search_agent(query)

async def query_documents_stream(query: str):
   return run_search_agent_stream(query)