from crewai.flow.flow import Flow, listen, start
from crewai import Agent
from crewai.tools import tool

from dotenv import load_dotenv
from litellm import completion
from TracingSchema import Monitor

import pm4py
import pandas
import datetime

load_dotenv()

eventLogPath = "Please provide the path of the event log."  

class singleAgentPmAnalyst(Flow):
    """This class implements the logic of the single agent system for process mining."""

    userQuery = input("Enter the desired Process Mining query: ")
    
    fileFormat = "" ## It is needed for the process analyst agent.
    monitor = Monitor("Please provide the path of JSON file which is used for the tracing schema.")

    NO_TOKEN_USAGE = 0
    NO_OUTPUT = "NO OUTPUT BECAUSE OF ERROR."

    startTime = ""
    endTime = ""
    status = "successful"


    @start()
    def dataPrep(self): ## No LLM usage, this is a deterministic agent.  

        self.startTime = str(datetime.datetime.now())

        if(eventLogPath.endswith (".csv")) : ## If the event log is in CSV format.
             self.fileFormat = "CSV"
             db = pandas.read_csv(eventLogPath)
        elif(eventLogPath.endswith (".xes")) : ## If the event log is in XES format.
             self.fileFormat = "XES"
             xesRead = pm4py.read_xes(eventLogPath)
             db = pm4py.convert_to_dataframe(xesRead)
        else:
            raise SystemExit("The file format is not supported!")

        numberOfRows = len(db) ## The number of rows.
        namesColumns = list(db.columns)  ## The names of columns.
        typesColumns = db.dtypes.astype(str).to_dict() ## The data types of columns.
        numberOfColumns = len(db.columns) ## The number of columns.

        metaDataDict = {"numberRows" : numberOfRows, "namesColumns" :namesColumns, 
                        "dataTypesColumns" : typesColumns, "numberColumns" : numberOfColumns}
        
        self.endTime = str(datetime.datetime.now())

        self.state["metaData"] = metaDataDict ## The profile of event log is needed for the process analyst agent.

        self.monitor.trace("dataPrep", "Data Profiler Agent", self.startTime, self.userQuery, 
                           metaDataDict, False, self.NO_TOKEN_USAGE, self.endTime, self.status)
        return metaDataDict


            
    @listen(dataPrep)
    def analyse(self): 
       
        processAnalyst = Agent( ## This is an LLM-based agent.
            role = "Process Analyst",
            goal = "Answer the query of user.",
            backstory = "You are the process analyst who answers the query of user.",
            tools = [self.executorTool], 
            verbose = True
            )

        input = f"Create a executable code without introducing it as a variable to answer \
            the user query: {self.userQuery} with regard to this data profile: {self.state["metaData"]}. \
            The path of the event log is available in the variable called: 'dataPath' and this event log is in dataformat:'{self.fileFormat}'. \
            If you want to read an event log in XES format, then use as import only 'pm4py' and use \
            the function 'pm4py.read_xes(file_path: str)' which returns <class 'pandas.DataFrame'>. \
            Then, save the final part needed for the answering user query in the variable called: 'execResults'.\
            Then, call the given tool 'executorTool' with the parameter: 'the whole generated code'. \
            Create a report briefly just about the result of the called tool 'executorTool' to answer the user query:'{self.userQuery}'."
        
        self.startTime = str(datetime.datetime.now())
        try:
            finalReport = processAnalyst.kickoff(input)
        except Exception as e:
            self.status = "failed"
            print(f"The error: '{e}' was occured!")
        self.endTime = str(datetime.datetime.now())

        if(self.status == "successful"):
            self.monitor.trace("Process Analyst", processAnalyst.role, self.startTime, input, 
                finalReport.raw, True, finalReport.usage_metrics, self.endTime, self.status)
            return finalReport
        else:
            self.monitor.trace("Process Analyst", processAnalyst.role, self.startTime, input, 
                self.NO_OUTPUT, True, finalReport.usage_metrics, self.endTime, self.status)
            raise SystemExit(f"A problem occurred in {processAnalyst.role}, so the system was terminated.")



    @tool("executorTool")
    def executorTool(codeToExecute: str): ## No LLM usage, this is a deterministic tool.
            """Execute the given code on the provided event log."""

            globalVariables = {}
            localVariables = {"dataPath": eventLogPath}
    
            try:
                exec(codeToExecute, globalVariables, localVariables)
                return localVariables["execResults"]
            except Exception as e:
                SystemExit(f"The error: '{e}' was occured!")
        
        
flow = singleAgentPmAnalyst()
flow.plot()
result = flow.kickoff()

print(f"Generated report: {result}")
