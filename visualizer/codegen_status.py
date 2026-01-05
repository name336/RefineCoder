"""Terminal-based status visualization for requirement-aware code generation."""

from typing import Optional
from colorama import Fore, Style, init
import sys

init()  # Initialize colorama


class CodegenStatusVisualizer:
    """Visualizes the workflow status of requirement codegen agents in the terminal."""

    def __init__(self):
        """Initialize the status visualizer."""
        self.active_agent: Optional[str] = None
        self.iteration: int = 0
        self._agent_art = {
            "analyzer": [
                "┌──────────┐",
                "│ ANALYZER │",
                "└──────────┘",
            ],
            "corrector": [
                "┌──────────┐",
                "│CORRECTOR │",
                "└──────────┘",
            ],
            "writer": [
                "┌──────────┐",
                "│  WRITER  │",
                "└──────────┘",
            ],
        }
        self._status_message = ""
        self._requirement_preview = ""

    def _clear_screen(self):
        """Clear the terminal screen."""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _get_agent_color(self, agent: str) -> str:
        """Get the color for an agent based on its state."""
        return Fore.GREEN if agent == self.active_agent else Fore.WHITE

    def set_requirement_preview(self, requirement: str, requirement_path: Optional[str] = None, max_length: int = 60):
        """Set a preview of the current requirement being processed.

        Args:
            requirement: The requirement text
            requirement_path: Optional file path to the requirement file
            max_length: Maximum length of the preview
        """
        if requirement_path:
            # Store the full requirement with file path for clickable link
            if len(requirement) > max_length:
                preview_text = requirement[:max_length - 3] + "..."
            else:
                preview_text = requirement
            self._requirement_preview = f"{preview_text} (Source: {requirement_path})"
        else:
            if len(requirement) > max_length:
                self._requirement_preview = requirement[:max_length - 3] + "..."
            else:
                self._requirement_preview = requirement

    def update(
        self,
        active_agent: str,
        iteration: int = 0,
        status_message: str = "",
        issues_count: int = 0,
    ):
        """Update the visualization with the current active agent and status.

        Args:
            active_agent: Name of the currently active agent (analyzer, corrector, writer)
            iteration: Current iteration number
            status_message: Current status message to display
            issues_count: Number of issues found (for analyzer)
        """
        self.active_agent = active_agent.lower()
        self.iteration = iteration
        self._status_message = status_message
        self._clear_screen()

        # Build the visualization
        lines = []

        # Add header
        lines.append(f"{Fore.CYAN}{Style.BRIGHT}Requirement Code Generation Workflow{Style.RESET_ALL}")
        lines.append("")

        # Display requirement preview if available
        if self._requirement_preview:
            lines.append(f"Requirement: {Fore.YELLOW}{self._requirement_preview}{Style.RESET_ALL}")
            lines.append("")

        # Display iteration info if applicable
        if self.iteration > 0:
            lines.append(f"Iteration: {Fore.CYAN}{self.iteration}{Style.RESET_ALL}")
            if issues_count > 0:
                lines.append(f"Issues found: {Fore.YELLOW}{issues_count}{Style.RESET_ALL}")
            lines.append("")

        # Workflow visualization
        # First row: Analyzer and Corrector (can loop)
        for i in range(3):
            analyzer_color = self._get_agent_color("analyzer")
            corrector_color = self._get_agent_color("corrector")
            line = (
                f"{analyzer_color}{self._agent_art['analyzer'][i]}"
                f"  ←→  "
                f"{corrector_color}{self._agent_art['corrector'][i]}"
                f"{Style.RESET_ALL}"
            )
            lines.append(line)

        lines.append("")  # Empty line between rows
        lines.append("         ↓")

        # Second row: Writer
        for i in range(3):
            writer_color = self._get_agent_color("writer")
            if i == 1:
                line = f"    {writer_color}{self._agent_art['writer'][i]}{Style.RESET_ALL}  →  Code"
            else:
                line = f"    {writer_color}{self._agent_art['writer'][i]}{Style.RESET_ALL}"
            lines.append(line)

        # Add status message
        if self._status_message:
            lines.append("")
            lines.append(f"Status: {Fore.YELLOW}{self._status_message}{Style.RESET_ALL}")

        # Print the visualization
        print("\n".join(lines))
        sys.stdout.flush()

    def reset(self):
        """Reset the visualization state."""
        self.active_agent = None
        self.iteration = 0
        self._status_message = ""
        self._requirement_preview = ""
        self._clear_screen()



