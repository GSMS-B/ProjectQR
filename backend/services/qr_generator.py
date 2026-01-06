"""
QRSecure QR Code Generator Service
Handles QR code generation with customization options.
"""

import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image
from typing import Optional, Tuple
import io
import base64


# Ensure qr_codes directory exists
QR_CODES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qr_codes")
os.makedirs(QR_CODES_DIR, exist_ok=True)


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def generate_qr_code(
    url: str,
    short_code: str,
    fill_color: str = "#000000",
    back_color: str = "#FFFFFF",
    logo_path: Optional[str] = None,
    style: str = "square"  # "square", "rounded", "dots"
) -> str:
    """
    Generate a QR code image and save it to disk.
    
    Args:
        url: The URL to encode in the QR code
        short_code: Unique identifier for filename
        fill_color: QR code color (hex)
        back_color: Background color (hex)
        logo_path: Optional path to logo image to embed
        style: QR code style - "square", "rounded", or "dots"
    
    Returns:
        Path to the saved QR code image
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for logo
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(url)
    qr.make(fit=True)
    
    # Convert colors
    fill_rgb = hex_to_rgb(fill_color)
    back_rgb = hex_to_rgb(back_color)
    
    # Create image with style
    if style == "rounded":
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(
                back_color=back_rgb,
                front_color=fill_rgb
            )
        )
    else:
        # Default square style
        img = qr.make_image(fill_color=fill_rgb, back_color=back_rgb)
    
    # Convert to PIL Image if needed
    if hasattr(img, 'get_image'):
        img = img.get_image()
    elif not isinstance(img, Image.Image):
        img = img.convert('RGB')
    
    # Ensure RGB mode
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Embed logo if provided
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path)
            
            # Calculate logo size (max 20% of QR code)
            qr_width, qr_height = img.size
            max_logo_size = int(min(qr_width, qr_height) * 0.2)
            
            # Resize logo maintaining aspect ratio
            logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
            
            # Calculate center position
            logo_width, logo_height = logo.size
            position = (
                (qr_width - logo_width) // 2,
                (qr_height - logo_height) // 2
            )
            
            # Create white background for logo
            logo_bg = Image.new('RGB', logo.size, back_rgb)
            
            # Handle transparency
            if logo.mode == 'RGBA':
                logo_bg.paste(logo, mask=logo.split()[3])
            else:
                logo_bg.paste(logo)
            
            # Paste logo onto QR code
            img.paste(logo_bg, position)
        except Exception as e:
            print(f"Warning: Could not embed logo: {e}")
    
    # Save image
    file_path = os.path.join(QR_CODES_DIR, f"{short_code}.png")
    img.save(file_path, "PNG")
    
    return file_path


def generate_qr_base64(
    url: str,
    fill_color: str = "#000000",
    back_color: str = "#FFFFFF"
) -> str:
    """
    Generate a QR code and return as base64 string (for API responses).
    
    Args:
        url: The URL to encode
        fill_color: QR code color (hex)
        back_color: Background color (hex)
    
    Returns:
        Base64-encoded PNG image string
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    
    qr.add_data(url)
    qr.make(fit=True)
    
    fill_rgb = hex_to_rgb(fill_color)
    back_rgb = hex_to_rgb(back_color)
    
    img = qr.make_image(fill_color=fill_rgb, back_color=back_rgb)
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Encode to base64
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def get_qr_image_path(short_code: str) -> Optional[str]:
    """
    Get the path to a QR code image if it exists.
    
    Args:
        short_code: The short code identifier
    
    Returns:
        Path to the image or None if not found
    """
    path = os.path.join(QR_CODES_DIR, f"{short_code}.png")
    return path if os.path.exists(path) else None


def delete_qr_image(short_code: str) -> bool:
    """
    Delete a QR code image from disk.
    
    Args:
        short_code: The short code identifier
    
    Returns:
        True if deleted, False if not found
    """
    path = os.path.join(QR_CODES_DIR, f"{short_code}.png")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
