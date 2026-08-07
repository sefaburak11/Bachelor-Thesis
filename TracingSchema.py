import json

class Monitor:

    def __init__(self, filePath):
        self.filePath = filePath
    
        with open(self.filePath, "a") as f:
            json.dump([],f)


    def trace(self, nameOfAgent, input, output, boolLLM):

        newObject = {
            "agentName": nameOfAgent,
            "input": input,
            "output": output,
            "boolLLM": boolLLM, 
            }


        with open(self.filePath, "r+") as f:
            traceElements = json.load(f)
            traceElements.append(newObject)
            f.seek(0)
            json.dump(traceElements, f, indent=4)