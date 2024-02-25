class Image:
    def __init__(self):
        self.image_in_roi, self.image_out_roi = None, None
        self.original_image = None
        self.original_image_data = None
        self.image_data = None
        self.shifted_ft_data = None
        self.ft_magnitude, self.ft_phase = None, None
        self.ft_real, self.ft_imaginary = None, None

    def attr(self, mode):
        return getattr(self, '_'.join(mode.split()).lower())