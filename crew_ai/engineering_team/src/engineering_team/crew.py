from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from .helper_utils import base_url, api_key



@CrewBase
class EngineeringTeam():
    """EngineeringTeam crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    llm_instance = LLM(
            base_url=base_url,
            api_key=api_key,
            model="gpt-5.1"
    )

    @agent
    def engineering_lead(self) -> Agent:
        self.llm_instance.model = "gpt-5.1"
        return Agent(
            llm = self.llm_instance,
            config=self.agents_config['engineering_lead'],
            verbose=True,
        )

    @agent
    def backend_engineer(self) -> Agent:
        self.llm_instance.model = "claude-sonnet-4-5"
        return Agent(
            llm = self.llm_instance,
            config=self.agents_config['backend_engineer'],
            verbose=True,
            allow_code_execution=True,
            # code_execution_mode="safe",  # Uses Docker for safety
            max_execution_time=500, 
            max_retry_limit=3 
        )
    
    @agent
    def frontend_engineer(self) -> Agent:
        self.llm_instance.model = "claude-sonnet-4"
        return Agent(
            llm = self.llm_instance,
            config=self.agents_config['frontend_engineer'],
            verbose=True,
        )
    
    @agent
    def test_engineer(self) -> Agent:
        self.llm_instance.model = "gpt-5.2"
        return Agent(
            llm = self.llm_instance,
            config=self.agents_config['test_engineer'],
            verbose=True,
            allow_code_execution=True,
            # code_execution_mode="safe",  # Uses Docker for safety
            max_execution_time=500, 
            max_retry_limit=3 
        )

    @task
    def design_task(self) -> Task:
        return Task(
            config=self.tasks_config['design_task']
        )

    @task
    def code_task(self) -> Task:
        return Task(
            config=self.tasks_config['code_task'],
        )

    @task
    def frontend_task(self) -> Task:
        return Task(
            config=self.tasks_config['frontend_task'],
        )

    @task
    def test_task(self) -> Task:
        return Task(
            config=self.tasks_config['test_task'],
        )   

    @crew
    def crew(self) -> Crew:
        """Creates the research crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )