"""Addtl file schemas use their own media island instead of root-only inputs."""
from pathlib import Path


def scoped_media_files(root, extensions):
    root = Path(root).resolve()
    island = root / "OvertliDS" / "addtl"
    if not island.is_dir():
        return []
    return sorted((p.relative_to(root).as_posix() for p in island.rglob("*")
                   if p.is_file() and p.suffix.lower() in extensions
                   and p.resolve().is_relative_to(island.resolve())), key=str.lower)


def _validate(file):
    import folder_paths
    island = (Path(folder_paths.get_input_directory()) / "OvertliDS" / "addtl").resolve()
    target = Path(folder_paths.get_annotated_filepath(file)).resolve()
    if not target.is_relative_to(island) or not target.is_file():
        return "Choose an existing reference inside input/OvertliDS/addtl."
    return True


def build_media_nodes():
    import sys
    nodes = sys.modules.get("nodes")
    if nodes is None or not hasattr(nodes, "LoadImage"):
        return {}
    import folder_paths
    from comfy_extras.nodes_video import LoadVideo
    from comfy_api.latest import io

    class OvertliAddtlLoadImage(nodes.LoadImage):
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"image": (scoped_media_files(folder_paths.get_input_directory(),
                {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}), {"image_upload": True})}}

        @classmethod
        def VALIDATE_INPUTS(cls, image):
            return _validate(image)

        def load_image(self, image):
            valid = _validate(image)
            if valid is not True:
                raise ValueError(valid)
            return super().load_image(image)

    class OvertliAddtlLoadVideo(LoadVideo):
        @classmethod
        def define_schema(cls):
            schema = super().define_schema()
            schema.node_id = "OvertliAddtlLoadVideo"
            schema.display_name = "OVERTLI Addtl Load Video"
            schema.inputs = [io.Combo.Input("file", options=scoped_media_files(
                folder_paths.get_input_directory(), {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}), upload=io.UploadType.video)]
            return schema

        @classmethod
        def validate_inputs(cls, file):
            return _validate(file)

        @classmethod
        def execute(cls, file):
            valid = _validate(file)
            if valid is not True:
                raise ValueError(valid)
            return super().execute(file)

    return {"OvertliAddtlLoadImage": OvertliAddtlLoadImage,
            "OvertliAddtlLoadVideo": OvertliAddtlLoadVideo}
