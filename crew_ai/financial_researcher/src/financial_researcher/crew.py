# src/financial_researcher/crew.py
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from fordllm.utils import TokenFetcher

@CrewBase
class ResearchCrew():
    """Research crew for comprehensive topic analysis and reporting"""
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    token_fetcher = TokenFetcher()
    base_url = "https://api.pivpn.core.ford.com/fordllmapi/api/v1"
    api_key = token_fetcher.token
    
    # Create LLM instance directly instead of using string from config
    llm_instance = LLM(
        base_url=base_url,
        api_key=api_key,
        model="gpt-5-mini"
    )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'],
            llm=self.llm_instance,
            verbose=True,
            tools=[SerperDevTool()]
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst'],
            llm=self.llm_instance,
            verbose=True
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task']
        )

    @task
    def analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['analysis_task'],
            output_file='output/report.md'
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