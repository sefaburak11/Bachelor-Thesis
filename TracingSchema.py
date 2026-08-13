import json

class Monitor:

    def __init__(self, filePath):
        self.filePath = filePath
    
        with open(self.filePath, "a") as f:
            json.dump([],f)


    def trace(self, nameOfAgent, role, startTimeStamp, input, output, boolLLM, tokenUsage, endTimeStamp, status):

        newObject = {
            "agentName": nameOfAgent,
            "agentRole" : role, 
            "startTimeStamp": startTimeStamp,
            "input": input,
            "output": output,
            "boolLLM": boolLLM,
            "tokenUsage": tokenUsage,
            "endTimeStamp": endTimeStamp,
            "status": status
            }


        with open(self.filePath, "r+") as f:
            traceElements = json.load(f)
            traceElements.append(newObject)
            f.seek(0)
            json.dump(traceElements, f, indent=4)