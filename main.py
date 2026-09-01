from crewai.flow.flow import Flow, listen, start
from crewai import Agent
from dotenv import load_dotenv
from litellm import completion
from TracingSchema import Monitor

import pm4py
import pandas
import datetime

load_dotenv()

class multiAgentPmAnalyst(Flow):

    counterTry = 0 ## The number shows the number of try of the analytical agent.
    MAXIMAL_TRY = 2 ## The number of maximal try to reproduce the code.

    userQuery = input("Enter the desired Process Mining query: ")

    eventLogPath =  r"ENTER THE DATA FILE NAME"    
    fileFormat = "" ## It is needed for the analytical agent.
    monitor = Monitor (r"ENTER THE JSON FILE NAME")

    NO_TOKEN_USAGE = 0
    NO_OUTPUT = "NO OUTPUT BECAUSE OF ERROR."

    startTime = ""
    endTime = ""
    status = "successful"


    @start()
    def dataPrep(self): ## No LLM usage, this is a deterministic agent.  

        self.startTime = str(datetime.datetime.now())

        if(self.eventLogPath.endswith (".csv")) : ## If the event log is in CSV format.
             self.fileFormat = "CSV"
             db = pandas.read_csv(self.eventLogPath)

        elif(self.eventLogPath.endswith (".xes")) : ## If the event log is in XES format.
             self.fileFormat = "XES"
             xesRead = pm4py.read_xes(self.eventLogPath)
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

        self.state["metaData"] = metaDataDict ## The profile of event log is needed for the analytical and judge agent.

        self.monitor.trace("dataPrep", "Data Profiler Agent", self.startTime, self.userQuery, 
                           metaDataDict , False, self.NO_TOKEN_USAGE, self.endTime, self.status)
        return metaDataDict
    




    @listen(dataPrep)
    def analyse(self): 
       
        while True:

            analyst = Agent( ## This is an LLM-based agent.
                role = "Analytical Agent",
                goal = "Create code for the required analyse." ,
                backstory = "You are the analyst who creates the code for the required analyse.", 
                verbose = True
                )

            input = f"Create a executable code without introducing it as a variable to answer \
            the user query: {self.userQuery} with regard to this data profile: {self.state["metaData"]}. \
            The path of the event log is available in the variable called: 'dataPath' and this event log is in dataformat:'{self.fileFormat}'. \
            If you want to read an event log in XES format, then use as import only 'pm4py' and use \
            the function 'pm4py.read_xes(file_path: str)' which returns <class 'pandas.DataFrame'>. \
            Finally, save the final part in the variable called: 'execResults' which is needed for the answering user query."


            self.startTime = str(datetime.datetime.now())
            try:
                generatedCode = analyst.kickoff(input)
            except Exception as e:
                self.status = "failed"
                print(f"The error: '{e}' was occured!")
            self.endTime = str(datetime.datetime.now())

            if(self.status == "successful"):
                self.monitor.trace("analyst", analyst.role, self.startTime, input, 
                                   generatedCode.raw, True, generatedCode.usage_metrics, self.endTime, self.status)
            else:
                self.monitor.trace("analyst", analyst.role, self.startTime, input, 
                                   self.NO_OUTPUT, True, generatedCode.usage_metrics, self.endTime, self.status)
                raise SystemExit(f"A problem occurred in {analyst.role}, so the system was terminated.")

            
            self.counterTry+=1
            if (self.check(generatedCode)) : ## If the generated code is approved by the judge agent.
                break
            elif (self.counterTry == self.MAXIMAL_TRY):
                raise SystemExit("The analytical agent generated incorrect code more than the maximum allowed number.")

            
        self.state["analyseResult"] = generatedCode ## It is needed for judge and executor agent.
        



    def check(self, code): ## The helper function for the judge agent to check the generated code.
         
        judge = Agent( ## This is an LLM-based agent.
            role = "Judge Agent",
            goal = "Evaluate the generated code.",
            backstory = "You are the judge who checks the code.",
            verbose = True
            )


        input = f"Return the boolean value 'True' if the code: {code} is appropriate for answering the user query:\
        {self.userQuery} with regard to this data profile: {self.state["metaData"]} and return 'False' if it is not.\
        Finally, state briefly the reason for the evaluation. The output should be in that form:\
        checkedAnswer:True/False, Reason:the reason for the evaluation."


        self.startTime = str(datetime.datetime.now())
        try:
            judgeResult = judge.kickoff(input)
        except Exception as e:
            self.status = "failed"
            print(f"The error: '{e}' was occured!")
        self.endTime = str(datetime.datetime.now())


        if(self.status == "successful"):
            self.monitor.trace("judge", judge.role, self.startTime, input, 
                    judgeResult.raw, True, judgeResult.usage_metrics, self.endTime, self.status)
        else:
            self.monitor.trace("judge", judge.role, self.startTime, input, 
                    self.NO_OUTPUT, True, judgeResult.usage_metrics, self.endTime, self.status)
            raise SystemExit(f"A problem occurred in {judge.role}, so the system was terminated.")
        

        
        approvalOfCode = ( ( (judgeResult.raw.split(","))[0] ).split(":") )[1] 
        ## Extract the True/False value after the execution of the judge agent.

        if(approvalOfCode == "True"):
            return True
        else:
            return False
        


    @listen(analyse) ## If the check of generated code is successful, this agent will be executed.
    def executor(self): ## No LLM usage, this is a deterministic agent.

        globalVariables = {}
        localVariables = {"dataPath": self.eventLogPath}
        codeToExecute = self.state["analyseResult"].raw

        self.startTime = str(datetime.datetime.now())
        try:
            exec(codeToExecute, globalVariables, localVariables)
        except Exception as e:
            self.status = "failed"
            print(f"The error: '{e}' was occured!")
        self.endTime = str(datetime.datetime.now())


        if(self.status == "successful"):
            self.state["executorOutcomes"] = localVariables["execResults"] ## It is needed for the reporter agent.
            self.monitor.trace("executor", "Executor Agent" , self.startTime, codeToExecute, 
                self.state["executorOutcomes"], False, self.NO_TOKEN_USAGE, self.endTime, self.status)
        else:
            self.monitor.trace("executor", "Executor Agent" ,self.startTime, codeToExecute, 
                self.NO_OUTPUT, False, self.NO_TOKEN_USAGE, self.endTime, self.status)
            raise SystemExit("A problem occurred in Executor Agent, so the system was terminated.")



    @listen(executor)
    def report(self): 

        reporter = Agent( ## This is an LLM-based agent. 
            role = "Reporter Agent",
            goal = "Create a report.",
            backstory = "You are a report writer that writes an understandable report for the user.",
            verbose = True
            )

        input = f"Create a report about the findings:'{self.state["executorOutcomes"]}' and the user query:'{self.userQuery}'."

        self.startTime = str(datetime.datetime.now())
        try:
            finalReport = reporter.kickoff(input)
        except Exception as e:
            self.status = "failed"
            print(f"The error: '{e}' was occured!")
        self.endTime = str(datetime.datetime.now())
        
        if(self.status == "successful"):
            self.monitor.trace("reporter", reporter.role, self.startTime, 
                    input, finalReport.raw, True, finalReport.usage_metrics, self.endTime, self.status)
            return finalReport
        else:
            self.monitor.trace("reporter", reporter.role, self.startTime, 
                    input, self.NO_OUTPUT, True, finalReport.usage_metrics, self.endTime, self.status)
            raise SystemExit(f"A problem occurred in {reporter.role}, so the system was terminated.")


flow = multiAgentPmAnalyst()
flow.plot()
result = flow.kickoff()

print(f"Generated report: {result}")