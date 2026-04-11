from __future__ import annotations

from .categories import cat_3d_cgi_stylized_3d
from .categories import abstract_art
from .categories import ai_webcam_work_call_virtual_meeting_video
from .categories import animation_cartoon_video_styles
from .categories import architecture_interior_environment
from .categories import branding_packaging_commercial_design
from .categories import card_collectible_formats
from .categories import casual_phone_photo_realism
from .categories import character_reference_turnarounds_anatomy
from .categories import craft_decorative_material_driven_styles
from .categories import document_business_templates
from .categories import editing_utility_styles
from .categories import editorial_marketing_cover_design
from .categories import experimental_generative
from .categories import game_world_specialized_visual_styles
from .categories import game_cinematic_utility
from .categories import highlight_recap_replay_styles
from .categories import illusions
from .categories import illustration_2d_stylized
from .categories import intro_outro_title_motion
from .categories import loop_wallpaper_background_motion
from .categories import other_misc
from .categories import painting_traditional_media
from .categories import patterns_optical_graphics
from .categories import pbr_texture_map_outputs
from .categories import photography_realism
from .categories import podcast_interview_talking_head_video
from .categories import print_stationery_event_materials
from .categories import screen_recordings_tutorials_streams
from .categories import selfie_mirror_live_phone_rear_camera_video
from .categories import shot_types
from .categories import special_effects_vision_modes
from .categories import symbolic_esoteric
from .categories import technical_diagram_medical_reference
from .categories import text_rendering_typography
from .categories import ui_product_mockups
from .categories import video_directing_scene_styles
from .categories import video_format_capture_era_styles

RAW_PROMPT_STYLES = [
    *cat_3d_cgi_stylized_3d.STYLES,
    *abstract_art.STYLES,
    *ai_webcam_work_call_virtual_meeting_video.STYLES,
    *animation_cartoon_video_styles.STYLES,
    *architecture_interior_environment.STYLES,
    *branding_packaging_commercial_design.STYLES,
    *card_collectible_formats.STYLES,
    *casual_phone_photo_realism.STYLES,
    *character_reference_turnarounds_anatomy.STYLES,
    *craft_decorative_material_driven_styles.STYLES,
    *document_business_templates.STYLES,
    *editing_utility_styles.STYLES,
    *editorial_marketing_cover_design.STYLES,
    *experimental_generative.STYLES,
    *game_world_specialized_visual_styles.STYLES,
    *game_cinematic_utility.STYLES,
    *highlight_recap_replay_styles.STYLES,
    *illusions.STYLES,
    *illustration_2d_stylized.STYLES,
    *intro_outro_title_motion.STYLES,
    *loop_wallpaper_background_motion.STYLES,
    *other_misc.STYLES,
    *painting_traditional_media.STYLES,
    *patterns_optical_graphics.STYLES,
    *pbr_texture_map_outputs.STYLES,
    *photography_realism.STYLES,
    *podcast_interview_talking_head_video.STYLES,
    *print_stationery_event_materials.STYLES,
    *screen_recordings_tutorials_streams.STYLES,
    *selfie_mirror_live_phone_rear_camera_video.STYLES,
    *shot_types.STYLES,
    *special_effects_vision_modes.STYLES,
    *symbolic_esoteric.STYLES,
    *technical_diagram_medical_reference.STYLES,
    *text_rendering_typography.STYLES,
    *ui_product_mockups.STYLES,
    *video_directing_scene_styles.STYLES,
    *video_format_capture_era_styles.STYLES,
]

CATEGORY_MODULES = {
    '3D / CGI / Stylized 3D': 'cat_3d_cgi_stylized_3d',
    'Abstract Art': 'abstract_art',
    'AI Webcam / Work-Call / Virtual Meeting Video': 'ai_webcam_work_call_virtual_meeting_video',
    'Animation / Cartoon Video Styles': 'animation_cartoon_video_styles',
    'Architecture / Interior / Environment': 'architecture_interior_environment',
    'Branding / Packaging / Commercial Design': 'branding_packaging_commercial_design',
    'Card / Collectible Formats': 'card_collectible_formats',
    'Casual Phone-Photo Realism': 'casual_phone_photo_realism',
    'Character Reference / Turnarounds / Anatomy': 'character_reference_turnarounds_anatomy',
    'Craft / Decorative / Material-Driven Styles': 'craft_decorative_material_driven_styles',
    'Document / Business Templates': 'document_business_templates',
    'Editing / Utility Styles': 'editing_utility_styles',
    'Editorial / Marketing / Cover Design': 'editorial_marketing_cover_design',
    'Experimental / Generative': 'experimental_generative',
    'Game / World / Specialized Visual Styles': 'game_world_specialized_visual_styles',
    'Game Cinematic Utility': 'game_cinematic_utility',
    'Highlight / Recap / Replay Styles': 'highlight_recap_replay_styles',
    'Illusions': 'illusions',
    'Illustration / 2D Stylized': 'illustration_2d_stylized',
    'Intro / Outro / Title Motion': 'intro_outro_title_motion',
    'Loop / Wallpaper / Background Motion': 'loop_wallpaper_background_motion',
    'Other / Misc': 'other_misc',
    'Painting / Traditional Media': 'painting_traditional_media',
    'Patterns / Optical Graphics': 'patterns_optical_graphics',
    'PBR / Texture / Map Outputs': 'pbr_texture_map_outputs',
    'Photography / Realism': 'photography_realism',
    'Podcast / Interview / Talking-Head Video': 'podcast_interview_talking_head_video',
    'Print / Stationery / Event Materials': 'print_stationery_event_materials',
    'Screen Recordings / Tutorials / Streams': 'screen_recordings_tutorials_streams',
    'Selfie / Mirror / Live Phone / Rear-Camera Video': 'selfie_mirror_live_phone_rear_camera_video',
    'Shot Types': 'shot_types',
    'Special Effects / Vision Modes': 'special_effects_vision_modes',
    'Symbolic / Esoteric': 'symbolic_esoteric',
    'Technical / Diagram / Medical / Reference': 'technical_diagram_medical_reference',
    'Text Rendering / Typography': 'text_rendering_typography',
    'UI / Product / Mockups': 'ui_product_mockups',
    'Video Directing / Scene Styles': 'video_directing_scene_styles',
    'Video Format / Capture / Era Styles': 'video_format_capture_era_styles',
}
