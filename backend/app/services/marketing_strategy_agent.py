"""
Marketing Strategy Agent Service

Generates a dedicated marketing strategy artifact from a completed report.
The strategy is stored separately from reports but reuses the same graph and
simulation retrieval tools to keep recommendations evidence-backed.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger
from .report_agent import (
    REACT_FORCE_FINAL_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG_ALT,
    REACT_OBSERVATION_TEMPLATE,
    REACT_TOOL_LIMIT_MSG,
    REACT_UNUSED_TOOLS_HINT,
    ReportAgent,
    ReportManager,
    ReportOutline,
    ReportSection,
)

logger = get_logger('miroshark.marketing_strategy_agent')


MARKETING_PLAN_SYSTEM_PROMPT = """\
You are a senior marketing strategist creating an evidence-backed action plan from a completed scenario research report.

[Primary Goal]
Convert the research outcome into a focused marketing strategy that identifies the major problems surfaced by the report and turns them into actionable solutions.

[Requirements]
1. Extract the most important market, positioning, trust, messaging, adoption, or channel problems from the report.
2. Prioritize problems by impact and urgency.
3. Design a strategy outline that helps a team tackle those problems one by one.
4. Keep the strategy grounded in the report evidence and simulation context; do not invent unsupported market facts.

[Output Format]
Return valid JSON in this exact structure:
{
  "title": "Marketing strategy title",
  "summary": "One-sentence strategy thesis",
  "problems": [
    {
      "problem": "Short problem label",
      "evidence": "What in the report supports this problem",
      "root_cause": "Why this problem exists",
      "recommended_actions": ["action 1", "action 2"],
      "solution": "Concise solution framing",
      "priority": "high|medium|low"
    }
  ],
  "sections": [
    {
      "title": "Section title",
      "description": "What this section covers"
    }
  ]
}

[Section Rules]
- Minimum 3 sections, maximum 5 sections.
- The sections should move from diagnosis to action.
- At least one section must directly address prioritized problem-by-problem actions.
"""

MARKETING_PLAN_USER_PROMPT_TEMPLATE = """\
[Scenario Requirement]
{simulation_requirement}

[Simulation Context]
- Total nodes: {total_nodes}
- Total edges: {total_edges}
- Entity types: {entity_types}
- Active entities: {total_entities}

[Source Report Excerpt]
{report_excerpt}

[Sample Related Facts]
{related_facts_json}

Identify the most important problems surfaced by this report and turn them into a marketing strategy structure. Focus on practical go-to-market, trust, messaging, channel, audience, and execution implications.
"""

MARKETING_SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are writing one section of a marketing strategy derived from a completed research report and simulation evidence.

Strategy title: {strategy_title}
Strategy thesis: {strategy_summary}
Scenario requirement: {simulation_requirement}
Source report ID: {report_id}
Current section: {section_title}

[Prioritized Problems]
{problems_json}

[Source Report Excerpt]
{report_excerpt}

[Writing Goal]
Produce a strategy section that is actionable, evidence-backed, and specific. Every recommendation must tie back to either the report, the simulation feed, or graph retrieval tools.

[Required Thinking]
- Diagnose the problem, not just the symptom.
- Explain why the issue matters for adoption, trust, conversion, retention, or narrative control.
- Propose actions a marketing team can actually execute.
- Call out risks and tradeoffs when relevant.
- Prefer concrete moves over generic advice.

[Tool Rules]
- Use at least 2 tool calls before finalizing.
- Start with simulation_feed when useful, then use graph retrieval tools to deepen evidence.
- Use interview_agents when first-person perspective would sharpen the recommendation.

[Format]
- Do not add Markdown headings inside the section.
- Use **bold**, quotes, and lists for structure.
- Write in English.
- Output only body content when you reach Final Answer.

[Available Retrieval Tools]
{tools_description}

[Response Modes]
Option A: Call a single tool using <tool_call> JSON.
Option B: Output final content starting with "Final Answer:".
Never do both in the same reply.
"""

MARKETING_SECTION_USER_PROMPT_TEMPLATE = """\
Completed strategy sections (avoid repetition):
{previous_content}

[Current Task]
Write section: {section_title}

[Problem Inventory]
{problems_json}

[Reminder]
1. Use the problems above as the decision frame.
2. Ground your claims in retrieved evidence.
3. End with concrete actions, solutions, or metrics when appropriate.
4. Do not add headings; write body text only.
"""


class MarketingStrategyLogger:
    """Structured JSONL logger for marketing strategy generation."""

    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER,
            'marketing_strategies',
            strategy_id,
            'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()

    def _ensure_log_file(self):
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

    def _get_elapsed_time(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    def log(
        self,
        action: str,
        stage: str,
        details: Dict[str, Any],
        section_title: Optional[str] = None,
        section_index: Optional[int] = None,
    ):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': round(self._get_elapsed_time(), 2),
            'strategy_id': self.strategy_id,
            'action': action,
            'stage': stage,
            'section_title': section_title,
            'section_index': section_index,
            'details': details,
        }
        with open(self.log_file_path, 'a', encoding='utf-8') as file_handle:
            file_handle.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def log_start(self, simulation_id: str, graph_id: str, report_id: str, simulation_requirement: str):
        self.log(
            action='report_start',
            stage='pending',
            details={
                'artifact_type': 'marketing_strategy',
                'simulation_id': simulation_id,
                'graph_id': graph_id,
                'report_id': report_id,
                'simulation_requirement': simulation_requirement,
                'message': 'Marketing strategy generation task started',
            },
        )

    def log_planning_start(self):
        self.log('planning_start', 'planning', {'message': 'Starting marketing strategy planning'})

    def log_planning_complete(self, outline_dict: Dict[str, Any], problems: List[Dict[str, Any]]):
        self.log(
            'planning_complete',
            'planning',
            {
                'message': 'Marketing strategy planning complete',
                'outline': outline_dict,
                'problems': problems,
            },
        )

    def log_section_start(self, section_title: str, section_index: int):
        self.log(
            'section_start',
            'generating',
            {'message': f'Starting section generation: {section_title}'},
            section_title=section_title,
            section_index=section_index,
        )

    def log_tool_call(self, section_title: str, section_index: int, tool_name: str, parameters: Dict[str, Any], iteration: int):
        self.log(
            'tool_call',
            'generating',
            {
                'iteration': iteration,
                'tool_name': tool_name,
                'parameters': parameters,
                'message': f'Calling tool: {tool_name}',
            },
            section_title=section_title,
            section_index=section_index,
        )

    def log_tool_result(self, section_title: str, section_index: int, tool_name: str, result: str, iteration: int):
        self.log(
            'tool_result',
            'generating',
            {
                'iteration': iteration,
                'tool_name': tool_name,
                'result': result,
                'result_length': len(result),
                'message': f'Tool {tool_name} returned result',
            },
            section_title=section_title,
            section_index=section_index,
        )

    def log_llm_response(self, section_title: str, section_index: int, response: str, iteration: int, has_tool_calls: bool, has_final_answer: bool):
        self.log(
            'llm_response',
            'generating',
            {
                'iteration': iteration,
                'response': response,
                'response_length': len(response),
                'has_tool_calls': has_tool_calls,
                'has_final_answer': has_final_answer,
                'message': f'LLM response (tool call: {has_tool_calls}, final answer: {has_final_answer})',
            },
            section_title=section_title,
            section_index=section_index,
        )

    def log_section_content(self, section_title: str, section_index: int, content: str, tool_calls_count: int):
        self.log(
            'section_content',
            'generating',
            {
                'content': content,
                'content_length': len(content),
                'tool_calls_count': tool_calls_count,
                'message': f'Section {section_title} content generation complete',
            },
            section_title=section_title,
            section_index=section_index,
        )

    def log_section_full_complete(self, section_title: str, section_index: int, full_content: str):
        self.log(
            'section_complete',
            'generating',
            {
                'content': full_content,
                'content_length': len(full_content),
                'message': f'Section {section_title} generation complete',
            },
            section_title=section_title,
            section_index=section_index,
        )

    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        self.log(
            'report_complete',
            'completed',
            {
                'artifact_type': 'marketing_strategy',
                'total_sections': total_sections,
                'total_time_seconds': round(total_time_seconds, 2),
                'message': 'Marketing strategy generation complete',
            },
        )

    def log_error(self, error_message: str, stage: str, section_title: Optional[str] = None):
        self.log(
            'error',
            stage,
            {
                'error': error_message,
                'message': f'Error occurred: {error_message}',
            },
            section_title=section_title,
        )


class MarketingStrategyConsoleLogger:
    """Plain-text console logger for marketing strategy generation."""

    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER,
            'marketing_strategies',
            strategy_id,
            'console_log.txt'
        )
        self._file_handler = None
        self._ensure_log_file()
        self._setup_file_handler()

    def _ensure_log_file(self):
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

    def _setup_file_handler(self):
        import logging

        self._file_handler = logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8')
        self._file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        self._file_handler.setFormatter(formatter)

        for logger_name in ('miroshark.marketing_strategy_agent', 'miroshark.report_agent', 'miroshark.graph_tools'):
            target_logger = logging.getLogger(logger_name)
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)

    def close(self):
        import logging

        if self._file_handler:
            for logger_name in ('miroshark.marketing_strategy_agent', 'miroshark.report_agent', 'miroshark.graph_tools'):
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

    def __del__(self):
        self.close()


class StrategyStatus(str, Enum):
    PENDING = 'pending'
    PLANNING = 'planning'
    GENERATING = 'generating'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class MarketingProblem:
    problem: str
    evidence: str = ''
    root_cause: str = ''
    recommended_actions: List[str] = field(default_factory=list)
    solution: str = ''
    priority: str = 'medium'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'problem': self.problem,
            'evidence': self.evidence,
            'root_cause': self.root_cause,
            'recommended_actions': self.recommended_actions,
            'solution': self.solution,
            'priority': self.priority,
        }


@dataclass
class MarketingStrategy:
    strategy_id: str
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: StrategyStatus
    outline: Optional[ReportOutline] = None
    problems: List[MarketingProblem] = field(default_factory=list)
    markdown_content: str = ''
    created_at: str = ''
    completed_at: str = ''
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_id': self.strategy_id,
            'report_id': self.report_id,
            'simulation_id': self.simulation_id,
            'graph_id': self.graph_id,
            'simulation_requirement': self.simulation_requirement,
            'status': self.status.value,
            'outline': self.outline.to_dict() if self.outline else None,
            'problems': [problem.to_dict() for problem in self.problems],
            'markdown_content': self.markdown_content,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'error': self.error,
        }


class MarketingStrategyManager:
    """Persistence and retrieval for marketing strategy artifacts."""

    STRATEGIES_DIR = os.path.join(Config.UPLOAD_FOLDER, 'marketing_strategies')

    @classmethod
    def _ensure_strategies_dir(cls):
        os.makedirs(cls.STRATEGIES_DIR, exist_ok=True)

    @classmethod
    def _get_strategy_folder(cls, strategy_id: str) -> str:
        return os.path.join(cls.STRATEGIES_DIR, strategy_id)

    @classmethod
    def _ensure_strategy_folder(cls, strategy_id: str) -> str:
        folder = cls._get_strategy_folder(strategy_id)
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def _get_meta_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'meta.json')

    @classmethod
    def _get_markdown_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'full_strategy.md')

    @classmethod
    def _get_outline_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'outline.json')

    @classmethod
    def _get_progress_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'progress.json')

    @classmethod
    def _get_section_path(cls, strategy_id: str, section_index: int) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), f'section_{section_index:02d}.md')

    @classmethod
    def _get_agent_log_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'agent_log.jsonl')

    @classmethod
    def _get_console_log_path(cls, strategy_id: str) -> str:
        return os.path.join(cls._get_strategy_folder(strategy_id), 'console_log.txt')

    @classmethod
    def get_console_log(cls, strategy_id: str, from_line: int = 0) -> Dict[str, Any]:
        log_path = cls._get_console_log_path(strategy_id)
        if not os.path.exists(log_path):
            return {'logs': [], 'total_lines': 0, 'from_line': 0, 'has_more': False}

        logs: List[str] = []
        total_lines = 0
        with open(log_path, 'r', encoding='utf-8') as file_handle:
            for index, line in enumerate(file_handle):
                total_lines = index + 1
                if index >= from_line:
                    logs.append(line.rstrip('\n\r'))
        return {'logs': logs, 'total_lines': total_lines, 'from_line': from_line, 'has_more': False}

    @classmethod
    def get_agent_log(cls, strategy_id: str, from_line: int = 0) -> Dict[str, Any]:
        log_path = cls._get_agent_log_path(strategy_id)
        if not os.path.exists(log_path):
            return {'logs': [], 'total_lines': 0, 'from_line': 0, 'has_more': False}

        logs: List[Dict[str, Any]] = []
        total_lines = 0
        with open(log_path, 'r', encoding='utf-8') as file_handle:
            for index, line in enumerate(file_handle):
                total_lines = index + 1
                if index >= from_line:
                    try:
                        logs.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        return {'logs': logs, 'total_lines': total_lines, 'from_line': from_line, 'has_more': False}

    @classmethod
    def save_outline(cls, strategy_id: str, outline: ReportOutline) -> None:
        cls._ensure_strategy_folder(strategy_id)
        with open(cls._get_outline_path(strategy_id), 'w', encoding='utf-8') as file_handle:
            json.dump(outline.to_dict(), file_handle, ensure_ascii=False, indent=2)

    @classmethod
    def save_section(cls, strategy_id: str, section_index: int, section: ReportSection) -> str:
        cls._ensure_strategy_folder(strategy_id)
        cleaned_content = ReportManager._clean_section_content(section.content, section.title)
        markdown = f'## {section.title}\n\n'
        if cleaned_content:
            markdown += f'{cleaned_content}\n\n'
        file_path = cls._get_section_path(strategy_id, section_index)
        with open(file_path, 'w', encoding='utf-8') as file_handle:
            file_handle.write(markdown)
        return file_path

    @classmethod
    def update_progress(
        cls,
        strategy_id: str,
        status: str,
        progress: int,
        message: str,
        current_section: Optional[str] = None,
        completed_sections: Optional[List[str]] = None,
    ) -> None:
        cls._ensure_strategy_folder(strategy_id)
        payload = {
            'status': status,
            'progress': progress,
            'message': message,
            'current_section': current_section,
            'completed_sections': completed_sections or [],
            'updated_at': datetime.now().isoformat(),
        }
        with open(cls._get_progress_path(strategy_id), 'w', encoding='utf-8') as file_handle:
            json.dump(payload, file_handle, ensure_ascii=False, indent=2)

    @classmethod
    def get_generated_sections(cls, strategy_id: str) -> List[Dict[str, Any]]:
        folder = cls._get_strategy_folder(strategy_id)
        if not os.path.exists(folder):
            return []

        sections: List[Dict[str, Any]] = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as file_handle:
                    content = file_handle.read()
                section_index = int(filename.replace('.md', '').split('_')[1])
                sections.append({
                    'filename': filename,
                    'section_index': section_index,
                    'content': content,
                })
        return sections

    @classmethod
    def assemble_full_strategy(cls, strategy_id: str, outline: ReportOutline) -> str:
        markdown = f'# {outline.title}\n\n'
        markdown += f'> {outline.summary}\n\n---\n\n'
        for section_info in cls.get_generated_sections(strategy_id):
            markdown += section_info['content']
        markdown = ReportManager._post_process_report(markdown, outline)
        with open(cls._get_markdown_path(strategy_id), 'w', encoding='utf-8') as file_handle:
            file_handle.write(markdown)
        return markdown

    @classmethod
    def save_strategy(cls, strategy: MarketingStrategy) -> None:
        cls._ensure_strategy_folder(strategy.strategy_id)
        with open(cls._get_meta_path(strategy.strategy_id), 'w', encoding='utf-8') as file_handle:
            json.dump(strategy.to_dict(), file_handle, ensure_ascii=False, indent=2)
        if strategy.outline:
            cls.save_outline(strategy.strategy_id, strategy.outline)
        if strategy.markdown_content:
            with open(cls._get_markdown_path(strategy.strategy_id), 'w', encoding='utf-8') as file_handle:
                file_handle.write(strategy.markdown_content)

    @classmethod
    def get_strategy(cls, strategy_id: str) -> Optional[MarketingStrategy]:
        path = cls._get_meta_path(strategy_id)
        if not os.path.exists(path):
            return None

        with open(path, 'r', encoding='utf-8') as file_handle:
            data = json.load(file_handle)

        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            outline = ReportOutline(
                title=outline_data.get('title', ''),
                summary=outline_data.get('summary', ''),
                sections=[
                    ReportSection(title=section.get('title', ''), content=section.get('content', ''))
                    for section in outline_data.get('sections', [])
                ],
            )

        markdown_content = data.get('markdown_content', '')
        if not markdown_content and os.path.exists(cls._get_markdown_path(strategy_id)):
            with open(cls._get_markdown_path(strategy_id), 'r', encoding='utf-8') as file_handle:
                markdown_content = file_handle.read()

        problems = [
            MarketingProblem(
                problem=item.get('problem', ''),
                evidence=item.get('evidence', ''),
                root_cause=item.get('root_cause', ''),
                recommended_actions=item.get('recommended_actions', []) or [],
                solution=item.get('solution', ''),
                priority=item.get('priority', 'medium'),
            )
            for item in data.get('problems', [])
        ]

        return MarketingStrategy(
            strategy_id=data['strategy_id'],
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=StrategyStatus(data['status']),
            outline=outline,
            problems=problems,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error'),
        )

    @classmethod
    def get_strategy_by_report(cls, report_id: str) -> Optional[MarketingStrategy]:
        cls._ensure_strategies_dir()
        for item in os.listdir(cls.STRATEGIES_DIR):
            item_path = os.path.join(cls.STRATEGIES_DIR, item)
            if not os.path.isdir(item_path):
                continue
            strategy = cls.get_strategy(item)
            if strategy and strategy.report_id == report_id:
                return strategy
        return None


class MarketingStrategyAgent(ReportAgent):
    """Dedicated post-report marketing strategy generator."""

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        report_id: str,
        source_report_markdown: str,
        llm_client=None,
        graph_tools=None,
    ):
        super().__init__(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            llm_client=llm_client,
            graph_tools=graph_tools,
        )
        self.source_report_id = report_id
        self.source_report_markdown = source_report_markdown or ''
        self.identified_problems: List[MarketingProblem] = []

    def _get_report_excerpt(self, max_chars: int = 12000) -> str:
        if not self.source_report_markdown:
            return '(No source report content available)'
        if len(self.source_report_markdown) <= max_chars:
            return self.source_report_markdown
        return self.source_report_markdown[:max_chars] + '\n\n... [Source report truncated] ...'

    def _serialize_problems(self) -> str:
        return json.dumps([problem.to_dict() for problem in self.identified_problems], ensure_ascii=False, indent=2)

    def plan_outline(self, progress_callback: Optional[Callable] = None) -> ReportOutline:
        logger.info('Starting marketing strategy planning...')
        if progress_callback:
            progress_callback('planning', 0, 'Analyzing source report and simulation context...')

        context = self.graph_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
        )

        if progress_callback:
            progress_callback('planning', 35, 'Extracting prioritized problems and strategy structure...')

        try:
            response = self.llm.chat_json(
                messages=[
                    {'role': 'system', 'content': MARKETING_PLAN_SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': MARKETING_PLAN_USER_PROMPT_TEMPLATE.format(
                            simulation_requirement=self.simulation_requirement,
                            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
                            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
                            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
                            total_entities=context.get('total_entities', 0),
                            report_excerpt=self._get_report_excerpt(10000),
                            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
                        ),
                    },
                ],
                temperature=0.2,
            )

            sections = [
                ReportSection(title=section_data.get('title', ''), content='')
                for section_data in response.get('sections', [])[:5]
                if section_data.get('title')
            ]
            if len(sections) < 3:
                sections = [
                    ReportSection(title='Priority Problem Map'),
                    ReportSection(title='Messaging and Audience Response Plan'),
                    ReportSection(title='Channel Execution and Success Metrics'),
                ]

            problems: List[MarketingProblem] = []
            for item in response.get('problems', [])[:8]:
                actions = item.get('recommended_actions', []) or []
                if isinstance(actions, str):
                    actions = [line.strip('- ').strip() for line in actions.splitlines() if line.strip()]
                problems.append(MarketingProblem(
                    problem=item.get('problem', '').strip(),
                    evidence=item.get('evidence', '').strip(),
                    root_cause=item.get('root_cause', '').strip(),
                    recommended_actions=actions,
                    solution=item.get('solution', '').strip(),
                    priority=(item.get('priority') or 'medium').strip().lower(),
                ))

            if not problems:
                problems = [
                    MarketingProblem(
                        problem='Unclear market-facing narrative',
                        evidence='The report indicates fragmented reactions and inconsistent interpretation across participants.',
                        root_cause='The current narrative does not clearly connect the offer to the audience’s primary concern.',
                        recommended_actions=[
                            'Define one primary message for the highest-priority audience segment',
                            'Align proof points and campaign assets to that message',
                        ],
                        solution='Create a single narrative spine with clear proof and repeated execution.',
                        priority='high',
                    )
                ]

            self.identified_problems = problems

            if progress_callback:
                progress_callback('planning', 100, 'Marketing strategy planning complete')

            return ReportOutline(
                title=response.get('title', 'Marketing Strategy Response Plan'),
                summary=response.get('summary', 'A focused action plan derived from the research outcome and simulation evidence.'),
                sections=sections,
            )

        except Exception as error:
            logger.error(f'Marketing strategy planning failed: {error}')
            self.identified_problems = [
                MarketingProblem(
                    problem='Market uncertainty around the scenario outcome',
                    evidence='The source report did not cleanly resolve how audiences interpret the scenario.',
                    root_cause='Audience concerns and proof points are not yet translated into a single action plan.',
                    recommended_actions=[
                        'Map each concern to a message and channel response',
                        'Prioritize execution for the highest-risk narrative gap',
                    ],
                    solution='Build a tightly prioritized messaging and activation plan anchored in the report evidence.',
                    priority='high',
                )
            ]
            return ReportOutline(
                title='Marketing Strategy Response Plan',
                summary='A prioritized plan to address the main problems surfaced by the report.',
                sections=[
                    ReportSection(title='Priority Problem Map'),
                    ReportSection(title='Action Plan by Problem'),
                    ReportSection(title='Execution Metrics and Risks'),
                ],
            )

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0,
    ) -> str:
        logger.info(f'ReACT generating marketing strategy section: {section.title}')
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)

        previous_content = '(This is the first section)'
        if previous_sections:
            previous_content = '\n\n---\n\n'.join(
                section_text[:4000] + '...' if len(section_text) > 4000 else section_text
                for section_text in previous_sections
            )

        system_prompt = MARKETING_SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            strategy_title=outline.title,
            strategy_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            report_id=self.source_report_id,
            section_title=section.title,
            problems_json=self._serialize_problems(),
            report_excerpt=self._get_report_excerpt(6000),
            tools_description=self._get_tools_description(),
        )
        user_prompt = MARKETING_SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
            problems_json=self._serialize_problems(),
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]

        tool_calls_count = 0
        max_iterations = 8
        min_tool_calls = 2
        conflict_retries = 0
        used_tools = set()
        all_tools = {'simulation_feed', 'insight_forge', 'panorama_search', 'quick_search', 'interview_agents'}
        report_context = f'Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}'

        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    'generating',
                    int((iteration / max_iterations) * 100),
                    f'Gathering evidence and drafting strategy ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})',
                )

            response = self.llm.chat(messages=messages, temperature=0.4, max_tokens=4096)
            if response is None:
                if iteration < max_iterations - 1:
                    messages.append({'role': 'assistant', 'content': '(Response was empty)'})
                    messages.append({'role': 'user', 'content': 'Please continue generating the strategy section.'})
                    continue
                break

            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = 'Final Answer:' in response

            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                if conflict_retries <= 2:
                    messages.append({'role': 'assistant', 'content': response})
                    messages.append({
                        'role': 'user',
                        'content': (
                            '[Format Error] Reply with either one tool call or Final Answer, not both. '
                            'Please respond again using only one format.'
                        ),
                    })
                    continue
                first_tool_end = response.find('</tool_call>')
                if first_tool_end != -1:
                    response = response[:first_tool_end + len('</tool_call>')]
                    tool_calls = self._parse_tool_calls(response)
                    has_tool_calls = bool(tool_calls)
                has_final_answer = False
                conflict_retries = 0

            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer,
                )

            if has_final_answer:
                if tool_calls_count < min_tool_calls:
                    unused_tools = all_tools - used_tools
                    unused_hint = (
                        f"(These tools haven't been used yet, try them: {', '.join(sorted(unused_tools))})"
                        if unused_tools else ''
                    )
                    messages.append({'role': 'assistant', 'content': response})
                    messages.append({
                        'role': 'user',
                        'content': REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                final_answer = response.split('Final Answer:')[-1].strip()
                if self.report_logger:
                    self.report_logger.log_section_content(section.title, section_index, final_answer, tool_calls_count)
                return final_answer

            if has_tool_calls:
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({'role': 'assistant', 'content': response})
                    messages.append({
                        'role': 'user',
                        'content': REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                call = tool_calls[0]
                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call['name'],
                        parameters=call.get('parameters', {}),
                        iteration=iteration + 1,
                    )

                result = self._execute_tool(call['name'], call.get('parameters', {}), report_context=report_context)

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call['name'],
                        result=result,
                        iteration=iteration + 1,
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])
                unused_tools = all_tools - used_tools
                unused_hint = ''
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=', '.join(sorted(unused_tools)))

                messages.append({'role': 'assistant', 'content': response})
                messages.append({
                    'role': 'user',
                    'content': REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call['name'],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=', '.join(sorted(used_tools)),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            messages.append({'role': 'assistant', 'content': response})
            if tool_calls_count < min_tool_calls:
                unused_tools = all_tools - used_tools
                unused_hint = (
                    f"(These tools haven't been used yet, try them: {', '.join(sorted(unused_tools))})"
                    if unused_tools else ''
                )
                messages.append({
                    'role': 'user',
                    'content': REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            final_answer = response.strip()
            if self.report_logger:
                self.report_logger.log_section_content(section.title, section_index, final_answer, tool_calls_count)
            return final_answer

        messages.append({'role': 'user', 'content': REACT_FORCE_FINAL_MSG})
        response = self.llm.chat(messages=messages, temperature=0.4, max_tokens=4096)
        if response is None:
            final_answer = '(This section generation failed: LLM returned empty response, please retry later)'
        elif 'Final Answer:' in response:
            final_answer = response.split('Final Answer:')[-1].strip()
        else:
            final_answer = response

        if self.report_logger:
            self.report_logger.log_section_content(section.title, section_index, final_answer, tool_calls_count)
        return final_answer

    def _generate_synthesis(self, generated_sections: List[str], outline: ReportOutline) -> Optional[str]:
        if len(generated_sections) < 2:
            return None

        content = '\n\n---\n\n'.join(section[:3000] for section in generated_sections)
        system_prompt = (
            'You are a senior marketing strategist synthesizing a strategy draft. '
            'Identify cross-cutting priorities, execution risks, and what must be measured.'
        )
        user_prompt = f"""\
Here are the strategy sections you have written:

{content}

Write a 250-400 word synthesis that answers:
1. What is the single most important strategic priority?
2. Which actions are prerequisites for the rest of the plan?
3. What execution risks or tradeoffs could undermine the strategy?
4. Which metrics should determine whether the plan is working?

Do not use headings. Use **bold** for emphasis where helpful.
"""
        try:
            response = self.llm.chat(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            if response:
                return response.strip()
        except Exception as error:
            logger.warning(f'Marketing strategy synthesis generation failed: {error}')
        return None

    def generate_strategy(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        strategy_id: Optional[str] = None,
    ) -> MarketingStrategy:
        import uuid

        if not strategy_id:
            strategy_id = f'strategy_{uuid.uuid4().hex[:12]}'

        start_time = datetime.now()
        strategy = MarketingStrategy(
            strategy_id=strategy_id,
            report_id=self.source_report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=StrategyStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )
        completed_section_titles: List[str] = []

        try:
            MarketingStrategyManager._ensure_strategy_folder(strategy_id)
            self.report_logger = MarketingStrategyLogger(strategy_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                report_id=self.source_report_id,
                simulation_requirement=self.simulation_requirement,
            )
            self.console_logger = MarketingStrategyConsoleLogger(strategy_id)

            MarketingStrategyManager.update_progress(strategy_id, 'pending', 0, 'Initializing marketing strategy...', completed_sections=[])
            MarketingStrategyManager.save_strategy(strategy)

            strategy.status = StrategyStatus.PLANNING
            MarketingStrategyManager.update_progress(strategy_id, 'planning', 5, 'Starting marketing strategy planning...', completed_sections=[])
            self.report_logger.log_planning_start()

            if progress_callback:
                progress_callback('planning', 0, 'Starting marketing strategy planning...')

            outline = self.plan_outline(
                progress_callback=lambda stage, progress, message: (
                    progress_callback(stage, progress // 5, message) if progress_callback else None
                )
            )
            strategy.outline = outline
            strategy.problems = list(self.identified_problems)

            self.report_logger.log_planning_complete(
                outline.to_dict(),
                [problem.to_dict() for problem in self.identified_problems],
            )

            MarketingStrategyManager.save_outline(strategy_id, outline)
            MarketingStrategyManager.update_progress(
                strategy_id,
                'planning',
                15,
                f'Marketing strategy planning complete, {len(outline.sections)} sections total',
                completed_sections=[],
            )
            MarketingStrategyManager.save_strategy(strategy)

            strategy.status = StrategyStatus.GENERATING
            generated_sections: List[str] = []
            total_sections = len(outline.sections)

            for index, section in enumerate(outline.sections):
                section_num = index + 1
                base_progress = 20 + int((index / total_sections) * 70)
                MarketingStrategyManager.update_progress(
                    strategy_id,
                    'generating',
                    base_progress,
                    f'Generating section: {section.title} ({section_num}/{total_sections})',
                    current_section=section.title,
                    completed_sections=completed_section_titles,
                )
                if progress_callback:
                    progress_callback('generating', base_progress, f'Generating section: {section.title} ({section_num}/{total_sections})')

                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, progress, message: (
                        progress_callback(stage, base_progress + int(progress * 0.7 / total_sections), message)
                        if progress_callback else None
                    ),
                    section_index=section_num,
                )

                section.content = section_content
                generated_sections.append(f'## {section.title}\n\n{section_content}')
                MarketingStrategyManager.save_section(strategy_id, section_num, section)
                completed_section_titles.append(section.title)

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=f'## {section.title}\n\n{section_content}'.strip(),
                    )

                MarketingStrategyManager.update_progress(
                    strategy_id,
                    'generating',
                    base_progress + int(70 / total_sections),
                    f'Section {section.title} completed',
                    current_section=None,
                    completed_sections=completed_section_titles,
                )

            if progress_callback:
                progress_callback('generating', 92, 'Synthesizing strategy priorities...')
            MarketingStrategyManager.update_progress(
                strategy_id,
                'generating',
                92,
                'Synthesizing strategy priorities...',
                completed_sections=completed_section_titles,
            )

            synthesis = self._generate_synthesis(generated_sections, outline)
            if synthesis:
                last_section = outline.sections[-1]
                last_section.content = (last_section.content or '') + '\n\n' + synthesis
                MarketingStrategyManager.save_section(strategy_id, len(outline.sections), last_section)
                generated_sections[-1] = f'## {last_section.title}\n\n{last_section.content}'

            if progress_callback:
                progress_callback('generating', 95, 'Assembling full marketing strategy...')
            MarketingStrategyManager.update_progress(
                strategy_id,
                'generating',
                95,
                'Assembling full marketing strategy...',
                completed_sections=completed_section_titles,
            )

            strategy.markdown_content = MarketingStrategyManager.assemble_full_strategy(strategy_id, outline)
            strategy.status = StrategyStatus.COMPLETED
            strategy.completed_at = datetime.now().isoformat()

            total_time_seconds = (datetime.now() - start_time).total_seconds()
            if self.report_logger:
                self.report_logger.log_report_complete(total_sections=total_sections, total_time_seconds=total_time_seconds)

            MarketingStrategyManager.save_strategy(strategy)
            MarketingStrategyManager.update_progress(
                strategy_id,
                'completed',
                100,
                'Marketing strategy generation complete',
                completed_sections=completed_section_titles,
            )
            if progress_callback:
                progress_callback('completed', 100, 'Marketing strategy generation complete')
            return strategy

        except Exception as error:
            logger.error(f'Marketing strategy generation failed: {error}')
            strategy.status = StrategyStatus.FAILED
            strategy.error = str(error)
            if self.report_logger:
                self.report_logger.log_error(str(error), stage='failed')
            MarketingStrategyManager.save_strategy(strategy)
            MarketingStrategyManager.update_progress(
                strategy_id,
                'failed',
                100,
                f'Marketing strategy generation failed: {error}',
                completed_sections=completed_section_titles,
            )
            return strategy

        finally:
            if self.console_logger:
                self.console_logger.close()