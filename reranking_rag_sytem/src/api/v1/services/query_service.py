from src.api.v1.agents.agents import run_search_agent, run_search_agent_stream
from src.core.guardrails import guard_input, guard_output


def query_documents(query: str):
   #Input guardrais: toxicity+topic restriction (may raise GuardrailViolation)
   guard_input(query)

   result = run_search_agent(query)
   if isinstance(result, dict) and result.get("answer"):
      result["answer"] = guard_output(result["answer"])

   # return run_search_agent(query)
   return result

async def query_documents_stream(query: str):
   #just return the async generator
   #input guardrails run before streaming begins.
   #(PII readaction is not applied to the token stream - see the guide)
   guard_input(query)
   return run_search_agent_stream(query)   
