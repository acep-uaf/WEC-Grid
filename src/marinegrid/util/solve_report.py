
# @dataclass
# class SolveReport:
#     """
#     Performance tracking for simulation runs.

#     Attributes:
#         simulation_time: Total wall time in seconds.
#         case: Case name/identifier.
#         backend: Backend name (e.g., "pypsa", "pandapower").
#         snapshots: List of snapshot timestamps.
#         converged: Per-step convergence flags.
#         solve_time: Power flow solve time per step.
#         solve_iterations: Solver iterations per step.
#         messages: Solver status messages per step.
#     """

#     simulation_time: float = 0.0
#     case: str = ""
#     backend: str = ""
#     snapshots: List = field(default_factory=list)
#     converged: List[bool] = field(default_factory=list)
#     solve_time: List[float] = field(default_factory=list)
#     solve_iterations: List[int] = field(default_factory=list)
#     messages: List[str] = field(default_factory=list)

#     def __repr__(self) -> str:
#         """Return a one-line summary of solve status and timing."""
#         if not self.converged:
#             status = "No runs"
#         elif all(self.converged):
#             status = "Converged"
#         else:
#             failed = sum(1 for c in self.converged if not c)
#             status = f"Failed ({failed}/{len(self.converged)})"

#         return (
#             f"SolveReport: {status}, "
#             f"steps={len(self.snapshots)}, "
#             f"time={self.simulation_time:.2f}s"
#         )

#     @validate_types
#     def add_solve_result(
#         self,
#         snapshot: pd.Timestamp,
#         converged: bool,
#         solve_time: float = 0.0,
#         iterations: int = 0,
#         message: str = "",
#     ) -> None:
#         """
#         Record solve result for a simulation step.

#         Args:
#             snapshot: Timestamp for this step.
#             converged: Whether power flow converged.
#             solve_time: Time to solve in seconds.
#             iterations: Number of solver iterations.
#             message: Solver status message.
#         """
#         self.snapshots.append(snapshot)
#         self.converged.append(converged)
#         self.solve_time.append(solve_time)
#         self.solve_iterations.append(iterations)
#         self.messages.append(message)

#     def to_dataframe(self) -> pd.DataFrame:
#         """
#         Convert report to DataFrame for analysis.

#         Returns:
#             DataFrame with columns for each metric.
#         """
#         return pd.DataFrame({
#             "snapshot": self.snapshots,
#             "converged": self.converged,
#             "solve_time": self.solve_time,
#             "iterations": self.solve_iterations,
#             "message": self.messages,
#         })
