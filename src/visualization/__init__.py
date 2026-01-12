"""
Visualization module - Heatmap rendering, Pareto plots, and graph generation.
"""

from .heatmap_renderer import (
    get_recommended_colormap,
    parse_heatmap_csv,
    render_all_heatmaps,
    render_heatmap_png,
    render_heatmap_with_critical_path_overlay,
)
from .pareto_plot import (
    create_pareto_evolution_animation,
    generate_pareto_evolution_animation,
    generate_pareto_frontier_per_stage,
    generate_pareto_visualization,
    plot_pareto_frontier_2d,
    save_pareto_plot,
)
from .stage_progression_plot import (
    generate_stage_progression_visualization,
    plot_stage_progression,
    save_stage_progression_plot,
)
from .trajectory_plot import (
    generate_hot_ratio_trajectory_chart,
    generate_wns_trajectory_chart,
    plot_hot_ratio_trajectory,
    plot_wns_trajectory,
    save_trajectory_plot,
)

__all__ = [
    "parse_heatmap_csv",
    "render_heatmap_png",
    "render_all_heatmaps",
    "get_recommended_colormap",
    "render_heatmap_with_critical_path_overlay",
    "plot_pareto_frontier_2d",
    "save_pareto_plot",
    "generate_pareto_visualization",
    "generate_pareto_frontier_per_stage",
    "create_pareto_evolution_animation",
    "generate_pareto_evolution_animation",
    "plot_wns_trajectory",
    "plot_hot_ratio_trajectory",
    "save_trajectory_plot",
    "generate_wns_trajectory_chart",
    "generate_hot_ratio_trajectory_chart",
    "plot_stage_progression",
    "save_stage_progression_plot",
    "generate_stage_progression_visualization",
]
