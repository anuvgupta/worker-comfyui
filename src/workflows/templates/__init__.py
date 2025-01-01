# templates package

# Calculate image height & width based on max size & aspect ratio
def calculate_dimensions(max_size: int, aspect_ratio: str) -> tuple[int, int]:
    # Parse aspect ratio string (e.g., "16:9" -> [16, 9])
    width_ratio, height_ratio = map(int, aspect_ratio.replace('_', ':').split(':'))
    
    # Calculate aspect ratio as a float
    ratio = width_ratio / height_ratio
    
    # If width is larger in the ratio (e.g., 16:9)
    if ratio > 1:
        width = max_size
        height = int(max_size / ratio)
    # If height is larger in the ratio (e.g., 9:16)
    else:
        height = max_size
        width = int(max_size * ratio)
    
    return width, height
