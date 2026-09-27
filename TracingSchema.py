import json

class Monitor:
    """This class implements a tracing schema for agentic systems."""

    def __init__(self, filePath):
        self.filePath = filePath
    
        with open(self.filePath, "a") as f:
            json.dump([],f)


    def trace(self, nameOfAgent, role, startTimeStamp, input, output, boolLLM, tokenUsage, endTimeStamp, status):

        newObject = {
            "agentName": nameOfAgent, ## The name of the agent. 
            "agentRole" : role,  ## The role of the agent. 
            "startTimeStamp": startTimeStamp, ## The timestamp for the start of the agent’s execution. 
            "input": input, ## The needed information for the agent's execution.
            "output": output, ## The produced information by the agent.
            "boolLLM": boolLLM, ## The information whether LLM is used by the agent.
            "tokenUsage": tokenUsage, ## The information about the amount of tokens used. This is relevant only for LLM-based agents.
            "endTimeStamp": endTimeStamp, ## The timestamp for the end of the agent’s execution. 
            "status": status ## The status of the agent. 
            }


        with open(self.filePath, "r+") as f:
            traceElements = json.load(f)
            traceElements.append(newObject)
            f.seek(0)
            json.dump(traceElements, f, indent=4)