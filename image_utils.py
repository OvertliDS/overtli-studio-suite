"""
OVERTLI STUDIO LLM Suite - Image Utilities

Handles all image format conversions between:
- Binary bytes (Pollinations response)
- ComfyUI IMAGE tensor [B, H, W, C] float32 0-1
- Base64 data URLs (LM Studio vision)
- Temporary files (Copilot CLI)
- PIL Images
- NumPy arrays
"""

from __future__ import annotations

import base64
import importlib
import io
import os
import tempfile
from typing import Any, Optional, Tuple, TypeAlias

from .exceptions import OvertliVisionError


# ============================================================================
# TYPE ALIASES
# ============================================================================

np = importlib.import_module("numpy")
torch = importlib.import_module("torch")
Image = importlib.import_module("PIL.Image")

ComfyImage: TypeAlias = Any  # Shape: [B, H, W, C], dtype: float32, range: 0-1


# ============================================================================
# BINARY TO COMFYUI TENSOR
# ============================================================================

def binary_to_comfy_image(image_bytes: bytes) -> ComfyImage:
    """
    Convert binary image data (PNG/JPEG) to ComfyUI IMAGE tensor.
    
    This is the primary conversion for Pollinations image responses.
    
    Args:
        image_bytes: Raw binary image data (PNG, JPEG, WebP, etc.)
    
    Returns:
        torch.Tensor: Shape [1, H, W, 3], dtype float32, values 0-1
    
    Raises:
        OvertliVisionError: If image cannot be decoded
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        return pil_to_comfy_image(pil_image)
    except Exception as e:
        raise OvertliVisionError(
            f"Failed to decode binary image: {e}",
            image_source="binary"
        )


def pil_to_comfy_image(pil_image: Any) -> ComfyImage:
    """
    Convert PIL Image to ComfyUI IMAGE tensor.
    
    Args:
        pil_image: PIL Image in any mode (RGB, RGBA, L, etc.)
    
    Returns:
        torch.Tensor: Shape [1, H, W, 3], dtype float32, values 0-1
    """
    # Convert to RGB (handles RGBA, L, P, etc.)
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    
    # To numpy: [H, W, C] uint8
    np_array = np.array(pil_image, dtype=np.float32) / 255.0
    
    # To torch: [1, H, W, C]
    tensor = torch.from_numpy(np_array).unsqueeze(0)
    
    return tensor


def numpy_to_comfy_image(np_array: Any) -> ComfyImage:
    """
    Convert NumPy array to ComfyUI IMAGE tensor.
    
    Args:
        np_array: Shape [H, W, C] or [H, W], uint8 or float32
    
    Returns:
        torch.Tensor: Shape [1, H, W, 3], dtype float32, values 0-1
    """
    # Handle grayscale
    if np_array.ndim == 2:
        np_array = np.stack([np_array] * 3, axis=-1)
    
    # Handle RGBA -> RGB
    if np_array.shape[-1] == 4:
        np_array = np_array[..., :3]
    
    # Normalize to 0-1 if uint8
    if np_array.dtype == np.uint8:
        np_array = np_array.astype(np.float32) / 255.0
    
    # To torch with batch dimension
    tensor = torch.from_numpy(np_array).unsqueeze(0)
    
    return tensor


# ============================================================================
# COMFYUI TENSOR TO OTHER FORMATS
# ============================================================================

def comfy_image_to_pil(tensor: ComfyImage, batch_index: int = 0) -> Any:
    """
    Convert ComfyUI IMAGE tensor to PIL Image.
    
    Args:
        tensor: ComfyUI IMAGE tensor [B, H, W, C]
        batch_index: Which image in the batch to convert
    
    Returns:
        PIL.Image.Image: RGB image
    """
    # Select batch item and convert to numpy
    np_array = tensor[batch_index].cpu().numpy()
    
    # Scale to 0-255 and convert to uint8
    np_array = (np_array * 255).clip(0, 255).astype(np.uint8)
    
    return Image.fromarray(np_array, mode="RGB")


def comfy_image_to_base64(
    tensor: ComfyImage,
    batch_index: int = 0,
    format: str = "PNG",
    quality: int = 95,
) -> str:
    """
    Convert ComfyUI IMAGE tensor to base64 data URL.
    
    This is the format required by LM Studio vision API.
    
    Args:
        tensor: ComfyUI IMAGE tensor [B, H, W, C]
        batch_index: Which image in the batch to convert
        format: Image format (PNG, JPEG, WEBP)
        quality: JPEG/WEBP quality (1-100)
    
    Returns:
        str: Base64 data URL (e.g., "data:image/png;base64,...")
    """
    pil_image = comfy_image_to_pil(tensor, batch_index)
    
    buffer = io.BytesIO()
    save_kwargs = {}
    if format.upper() in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality
    
    pil_image.save(buffer, format=format, **save_kwargs)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    mime_type = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "WEBP": "image/webp",
    }.get(format.upper(), "image/png")
    
    return f"data:{mime_type};base64,{encoded}"


def comfy_image_to_tempfile(
    tensor: ComfyImage,
    batch_index: int = 0,
    format: str = "png",
    prefix: str = "overtli_",
    temp_dir: Optional[str] = None,
) -> str:
    """
    Save ComfyUI IMAGE tensor to a temporary file.
    
    This is used for Copilot CLI which requires a file path.
    
    Args:
        tensor: ComfyUI IMAGE tensor [B, H, W, C]
        batch_index: Which image in the batch to save
        format: File extension (png, jpg, webp)
        prefix: Filename prefix
        temp_dir: Directory for temp files (uses system temp if None)
    
    Returns:
        str: Absolute path to the temporary file
    
    Note:
        Caller is responsible for cleanup via cleanup_temp_file()
    """
    pil_image = comfy_image_to_pil(tensor, batch_index)
    
    # Create temp file with proper extension
    suffix = f".{format.lower()}"
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
    os.close(fd)
    
    # Save image
    save_kwargs = {}
    if format.lower() in ("jpg", "jpeg", "webp"):
        save_kwargs["quality"] = 95
    
    pil_image.save(path, **save_kwargs)
    
    return path


def cleanup_temp_file(path: str) -> bool:
    """
    Safely remove a temporary file.
    
    Args:
        path: Path to the file to remove
    
    Returns:
        bool: True if removed, False if file didn't exist or error
    """
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except OSError:
        return False


# ============================================================================
# FILE PATH TO COMFYUI TENSOR
# ============================================================================

def load_image_from_path(file_path: str) -> ComfyImage:
    """
    Load an image file as ComfyUI IMAGE tensor.
    
    Args:
        file_path: Path to image file
    
    Returns:
        torch.Tensor: Shape [1, H, W, 3], dtype float32, values 0-1
    
    Raises:
        OvertliVisionError: If file cannot be loaded
    """
    try:
        pil_image = Image.open(file_path)
        return pil_to_comfy_image(pil_image)
    except FileNotFoundError:
        raise OvertliVisionError(
            f"Image file not found: {file_path}",
            image_source="file_path"
        )
    except Exception as e:
        raise OvertliVisionError(
            f"Failed to load image from {file_path}: {e}",
            image_source="file_path"
        )


# ============================================================================
# BASE64 TO COMFYUI TENSOR
# ============================================================================

def base64_to_comfy_image(data_url: str) -> ComfyImage:
    """
    Convert base64 data URL to ComfyUI IMAGE tensor.
    
    Args:
        data_url: Base64 data URL (e.g., "data:image/png;base64,...")
    
    Returns:
        torch.Tensor: Shape [1, H, W, 3], dtype float32, values 0-1
    
    Raises:
        OvertliVisionError: If data URL is invalid
    """
    try:
        # Handle both with and without data URL prefix
        if data_url.startswith("data:"):
            # Extract base64 portion after the comma
            _, encoded = data_url.split(",", 1)
        else:
            encoded = data_url
        
        image_bytes = base64.b64decode(encoded)
        return binary_to_comfy_image(image_bytes)
    
    except Exception as e:
        raise OvertliVisionError(
            f"Failed to decode base64 image: {e}",
            image_source="base64"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_image_dimensions(tensor: ComfyImage) -> Tuple[int, int, int]:
    """
    Get dimensions of a ComfyUI IMAGE tensor.
    
    Args:
        tensor: ComfyUI IMAGE tensor [B, H, W, C]
    
    Returns:
        Tuple[int, int, int]: (batch_size, height, width)
    """
    return tensor.shape[0], tensor.shape[1], tensor.shape[2]


def validate_comfy_image(tensor: Any, name: str = "image") -> None:
    """
    Validate that a tensor is a proper ComfyUI IMAGE.
    
    Args:
        tensor: Tensor to validate
        name: Name for error messages
    
    Raises:
        OvertliVisionError: If tensor is invalid
    """
    if not isinstance(tensor, torch.Tensor):
        raise OvertliVisionError(
            f"{name} must be a torch.Tensor, got {type(tensor).__name__}",
            image_source="validation"
        )
    
    if tensor.ndim != 4:
        raise OvertliVisionError(
            f"{name} must be 4D [B,H,W,C], got {tensor.ndim}D",
            image_source="validation"
        )
    
    if tensor.shape[-1] != 3:
        raise OvertliVisionError(
            f"{name} must have 3 channels, got {tensor.shape[-1]}",
            image_source="validation"
        )
    
    if tensor.dtype != torch.float32:
        raise OvertliVisionError(
            f"{name} must be float32, got {tensor.dtype}",
            image_source="validation"
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Type alias
    "ComfyImage",
    
    # Binary/bytes conversions
    "binary_to_comfy_image",
    
    # PIL conversions
    "pil_to_comfy_image",
    "comfy_image_to_pil",
    
    # NumPy conversions
    "numpy_to_comfy_image",
    
    # Base64 conversions
    "comfy_image_to_base64",
    "base64_to_comfy_image",
    
    # File operations
    "comfy_image_to_tempfile",
    "load_image_from_path",
    "cleanup_temp_file",
    
    # Utilities
    "get_image_dimensions",
    "validate_comfy_image",
]
