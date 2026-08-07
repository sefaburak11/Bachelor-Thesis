from crewai.flow.flow import Flow, listen, start
from crewai import Agent
from dotenv import load_dotenv
from litellm import completion

from TracingSchema import Monitor

import pm4py
import pandas


load_dotenv()

class pmAnalytics(Flow):

    counterTry = 0 ## number shows the number of try of analytical agent
    MAXIMAL_TRY = 2 ## number of maximal try to reproduce the code

    userQuery = input("Enter the desired Process Mining query: ")
    
    eventLogPath =  r"ENTER THE DATA FILE NAME"
    
    fileFormat = "" ##it is needed for analytical agent

    monitor = Monitor (r"ENTER THE JSON FILE NAME")

    @start()
    def dataPrep(self): ##no LLM, just deterministic
        
        if(self.eventLogPath.endswith (".csv")) : ## if data in csv format
             self.fileFormat = "CSV"
             print("CSV ENTERED!")
             
             db = pandas.read_csv(self.eventLogPath)
        elif(self.eventLogPath.endswith (".xes")) : ## if data in xes format
             self.fileFormat = "XES"
             xesRead = pm4py.read_xes(self.eventLogPath)
             db = pm4py.convert_to_dataframe(xesRead)
        else:
            raise SystemExit("The fileformat is not supported!")
        
        
        numberOfRows = len(db) ## number of rows
        namesColumns = list(db.columns)  ## names of columns
        typesColumns = db.dtypes.astype(str).to_dict() ## types of columns
        numberOfColumns = len(db.columns) ## number of columns

        metaDataDict = {"numberRows" : numberOfRows, 
                    "namesColumns" :namesColumns,
                    "typesColumns" : typesColumns, 
                    "numberColumns" : numberOfColumns
                        }
        
        self.state["metaData"] = metaDataDict ##needed for analytical and judge agent

        self.monitor.trace("dataPrep", self.userQuery, metaDataDict ,False)

        return metaDataDict
    

   
    @listen(dataPrep)
    def analyse(self): 
       
        while True:

            analyst = Agent( #Agent with LLM
                role="Analytical Agent",

                goal= f"Return code without introducing it as a variable for the required analyse \
                based on the user query: {self.userQuery} and profiled dataset: {self.state["metaData"]}",

                backstory="You are the analystics that creates the code for the required analyse." \
                f"The path of given event log is available in a variable called 'dataPath' and the event log is in dataformat: '{self.fileFormat}'." \
                "If you want to read an event log in XES format, then use as import just 'pm4py' and the function 'pm4py.read_xes(file_path: str)' and " \
                "the function 'pm4py.read_xes(file_path: str) returns <class 'pandas.DataFrame'>. " \
                "Moreover, save the final part in 'execResults' variable which is needed for the answering query.",

                verbose=True
                )

            input = f"Create a executable code for the {self.userQuery} and {self.state["metaData"]}"
            generatedCode = analyst.kickoff(input)

            self.counterTry+=1

            if (self.check(generatedCode)) : ## if the generated code is approved
                break

            elif (self.counterTry == self.MAXIMAL_TRY):
                 raise SystemExit("The analyst agent generated incorrect code more than the maximum number of times.")


        self.state["analyseResult"] = generatedCode ## needed for judge, executor agent


        self.monitor.trace("analyst", input, self.state["analyseResult"].raw , True)



    def check(self, code): ## helper function (judge Agent) for checking the generated code by an LLM
         
        judge = Agent( #Agent with LLM
            role="Judge Agent",
            goal= f"Return the value 'True' if you think that generated code {code} is appropriate for the {self.state["metaData"]} \
            to answer the question: {self.userQuery} and return 'False' otherwise. After that give a reason for that very briefly.",
            backstory= f"The path of the data to analyze is in a variable called 'dataPath' \
            and it is in dataformat: {self.fileFormat}. \
            Your output should be in form: checkedAnswer:True/False,Reason:your reason" ,
            verbose=True
            )


        input = f"Return the boolean value true if this code :{code} is good for answering this query :{self.userQuery} specifically for this {self.state["metaData"]} and return false if not"
        approve = judge.kickoff(input)

        self.monitor.trace("judge", input, approve.raw , True)
        
        approveValue = ( ( (approve.raw.split(","))[0] ).split(":") )[1] ##extract the true/false value for the generated code
        
        if (approveValue == "True") :
            print("ENTERED THE TRUE CASE")
            return True
        else :
            print("ENTERED THE FALSE CASE")
            return False
        

    @listen(analyse) ## if the code was approved
    def executor(self): #no LLM, just deterministic

        globalVariables = {}

        localVariables = {"dataPath" : self.eventLogPath}
        
        codeToExecute = self.state["analyseResult"].raw

        exec(codeToExecute, globalVariables, localVariables)

        self.state["executorArtifacts"] = localVariables["execResults"] ## needed for report agent

        self.monitor.trace("executor", codeToExecute, localVariables["execResults"] , False)



    @listen(executor)
    def report(self): 

        reporter = Agent( #Agent with LLM
            role="Reporter",
            goal= f"Report the results: {self.state["executorArtifacts"]} for the query:{self.userQuery}",
            backstory="You are the reporter that reports the results in a understandable way for the user.",
            verbose=True
            )

        input = f"Give me a report about the results: '{self.state["executorArtifacts"]}' and my query: '{self.userQuery}'"

        finalReport = reporter.kickoff(input)

        self.monitor.trace("reporter", input, finalReport.raw , True)

        return finalReport




flow = pmAnalytics()
flow.plot()
result = flow.kickoff()

print(f"Generated report: {result}")