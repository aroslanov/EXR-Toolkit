"""
Processing executor - applies filters to images via OpenImageIO.

This module bridges the processing pipeline to OIIO's ImageBufAlgo
functions, handling the actual image processing operations.
"""

from typing import Optional
import OpenImageIO as oiio

from .pipeline import ProcessingPipeline
from .filters import (
    ProcessingFilter,
    MedianFilter,
    UnsharpMaskFilter,
    ColorSpaceConversionFilter,
    BrightnessContrastFilter,
    GammaCorrectionFilter,
    FillHolesFilter,
    FixNonFiniteFilter,
    WarpTransformFilter,
    RotateFilter,
    NoiseInjectionFilter,
    DilateFilter,
    ErodeFilter,
    ChannelExtractFilter,
    ChannelInvertFilter,
)


class ProcessingExecutor:
    """Executes processing pipeline on ImageBuf objects."""
    
    def execute(
        self,
        imagebuf: oiio.ImageBuf,
        pipeline: ProcessingPipeline,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """
        Apply all enabled filters in pipeline to image sequentially.
        
        Args:
            imagebuf: Input image buffer
            pipeline: Processing pipeline with filters
            roi: Optional region of interest to process
        
        Returns:
            Processed image buffer
        """
        if not pipeline.enabled or pipeline.is_empty():
            return imagebuf
        
        result = imagebuf
        for filter in pipeline.get_enabled_filters():
            result = self._apply_filter(result, filter, roi)
            if not result:
                raise RuntimeError(f"Filter {filter.name} failed to process image")
        
        return result
    
    def _apply_filter(
        self,
        imagebuf: oiio.ImageBuf,
        filter: ProcessingFilter,
        roi: Optional[oiio.ROI] = None
    ) -> Optional[oiio.ImageBuf]:
        """
        Apply a single filter to image buffer.
        
        Args:
            imagebuf: Input image buffer
            filter: Filter to apply
            roi: Optional region of interest
        
        Returns:
            Processed image buffer, or None if filter failed
        """
        try:
            # Validate filter parameters
            is_valid, errors = filter.validate_parameters()
            if not is_valid:
                raise ValueError(f"Invalid filter parameters: {errors}")
            
            # Dispatch to appropriate handler
            if isinstance(filter, MedianFilter):
                return self._apply_median_filter(imagebuf, filter, roi)
            
            elif isinstance(filter, UnsharpMaskFilter):
                return self._apply_unsharp_mask(imagebuf, filter, roi)
            
            elif isinstance(filter, ColorSpaceConversionFilter):
                return self._apply_color_space_conversion(imagebuf, filter, roi)
            
            elif isinstance(filter, BrightnessContrastFilter):
                return self._apply_brightness_contrast(imagebuf, filter, roi)
            
            elif isinstance(filter, GammaCorrectionFilter):
                return self._apply_gamma_correction(imagebuf, filter, roi)
            
            elif isinstance(filter, FillHolesFilter):
                return self._apply_fill_holes(imagebuf, filter, roi)
            
            elif isinstance(filter, FixNonFiniteFilter):
                return self._apply_fix_non_finite(imagebuf, filter, roi)
            
            elif isinstance(filter, WarpTransformFilter):
                return self._apply_warp_transform(imagebuf, filter, roi)
            
            elif isinstance(filter, RotateFilter):
                return self._apply_rotate(imagebuf, filter, roi)
            
            elif isinstance(filter, NoiseInjectionFilter):
                return self._apply_noise_injection(imagebuf, filter, roi)
            
            elif isinstance(filter, DilateFilter):
                return self._apply_dilate(imagebuf, filter, roi)
            
            elif isinstance(filter, ErodeFilter):
                return self._apply_erode(imagebuf, filter, roi)
            
            elif isinstance(filter, ChannelExtractFilter):
                return self._apply_channel_extract(imagebuf, filter, roi)
            
            elif isinstance(filter, ChannelInvertFilter):
                return self._apply_channel_invert(imagebuf, filter, roi)
            
            else:
                raise ValueError(f"Unknown filter type: {type(filter)}")
        
        except Exception as e:
            print(f"[ERROR] Failed to apply filter {filter.name}: {e}")
            return None
    
    def _apply_median_filter(
        self,
        imagebuf: oiio.ImageBuf,
        filter: MedianFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply median filter."""
        width_param = filter.get_parameter("kernel_width")
        height_param = filter.get_parameter("kernel_height")
        
        if not width_param or not height_param:
            raise ValueError("Missing kernel_width or kernel_height parameter")
        
        width = width_param.value
        height = height_param.value
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.median_filter(imagebuf, width, height)
        
        if result is None or result.has_error():
            raise RuntimeError("median_filter failed")
        
        return result
    
    def _apply_unsharp_mask(
        self,
        imagebuf: oiio.ImageBuf,
        filter: UnsharpMaskFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply unsharp mask."""
        amount_param = filter.get_parameter("amount")
        radius_param = filter.get_parameter("radius")
        threshold_param = filter.get_parameter("threshold")
        
        if not all([amount_param, radius_param, threshold_param]):
            raise ValueError("Missing filter parameters")
        
        amount = amount_param.value if amount_param else 0
        radius = radius_param.value if radius_param else 0
        threshold = threshold_param.value if threshold_param else 0
        
        # OIIO 2.0+ API: unsharp_mask(src, kernel="gaussian", width=radius, amount=amount, threshold=threshold)
        result = oiio.ImageBufAlgo.unsharp_mask(
            imagebuf,
            kernel="gaussian",
            width=radius,
            amount=amount,
            threshold=threshold
        )
        
        if result is None or result.has_error():
            raise RuntimeError("unsharp_mask failed")
        
        return result
    
    def _apply_color_space_conversion(
        self,
        imagebuf: oiio.ImageBuf,
        filter: ColorSpaceConversionFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply color space conversion."""
        from_param = filter.get_parameter("from_space")
        to_param = filter.get_parameter("to_space")
        unpremult_param = filter.get_parameter("unpremult")
        
        if not all([from_param, to_param, unpremult_param]):
            raise ValueError("Missing color space conversion parameters")
        
        from_space = from_param.value if from_param else None
        to_space = to_param.value if to_param else None
        unpremult = unpremult_param.value if unpremult_param else None
        
        if from_space is None or to_space is None or unpremult is None:
            raise ValueError("Color space conversion parameters have no value")
        
        # OIIO 2.0+ API: colorconvert(src, from_space, to_space, unpremult)
        result = oiio.ImageBufAlgo.colorconvert(
            imagebuf,
            from_space,
            to_space,
            unpremult
        )
        
        if result is None or result.has_error():
            raise RuntimeError(f"colorconvert from {from_space} to {to_space} failed")
        
        return result
    
    def _apply_brightness_contrast(
        self,
        imagebuf: oiio.ImageBuf,
        filter: BrightnessContrastFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply brightness/contrast adjustment."""
        brightness_param = filter.get_parameter("brightness")
        contrast_param = filter.get_parameter("contrast")
        
        if not all([brightness_param, contrast_param]):
            raise ValueError("Missing brightness/contrast parameters")
        
        brightness = brightness_param.value if brightness_param else 1.0
        contrast = contrast_param.value if contrast_param else 1.0
        
        # Apply contrast first (multiply), then brightness (add)
        result = imagebuf
        
        # Contrast: (pixel - 0.5) * contrast + 0.5 using OIIO 2.0+ API
        if contrast != 1.0:
            # Subtract 0.5, multiply by contrast, add 0.5
            temp1 = oiio.ImageBufAlgo.add(result, (-0.5, -0.5, -0.5, 0))
            temp2 = oiio.ImageBufAlgo.mul(temp1, (contrast, contrast, contrast, 1))
            result = oiio.ImageBufAlgo.add(temp2, (0.5, 0.5, 0.5, 0))
        
        # Brightness: multiply by brightness factor
        if brightness != 1.0:
            result = oiio.ImageBufAlgo.mul(result, (brightness, brightness, brightness, 1))
        
        return result
    
    def _apply_gamma_correction(
        self,
        imagebuf: oiio.ImageBuf,
        filter: GammaCorrectionFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply gamma correction."""
        gamma_param = filter.get_parameter("gamma")
        
        if not gamma_param:
            raise ValueError("Missing gamma parameter")
        
        gamma = gamma_param.value
        
        if gamma == 1.0:
            return imagebuf
        
        # gamma correction: pixel^(1/gamma)
        # Use colorconvert with gamma if available, otherwise use matrix
        result = oiio.ImageBuf()
        
        # OIIO has limited direct gamma support, so we'll use a simple approximation
        # via colormatrixtransform or by using pixelmath
        # For now, use identity (TODO: implement proper gamma via custom code)
        result = imagebuf
        
        return result
    
    def _apply_fill_holes(
        self,
        imagebuf: oiio.ImageBuf,
        filter: FillHolesFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply fill holes (push-pull) algorithm."""
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.fillholes_pushpull(imagebuf)
        
        if result is None or result.has_error():
            raise RuntimeError("fillholes_pushpull failed")
        
        return result
    
    def _apply_fix_non_finite(
        self,
        imagebuf: oiio.ImageBuf,
        filter: FixNonFiniteFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Replace NaN and Infinity values."""
        fill_param = filter.get_parameter("fill_value")
        
        if not fill_param:
            raise ValueError("Missing fill_value parameter")
        
        fill_value = fill_param.value
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.fixNonFinite(imagebuf)
        
        if result is None or result.has_error():
            raise RuntimeError("fixNonFinite failed")
        
        return result
    
    def _apply_warp_transform(
        self,
        imagebuf: oiio.ImageBuf,
        filter: WarpTransformFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply geometric warp transform."""
        mode_param = filter.get_parameter("matrix_mode")
        
        if not mode_param:
            raise ValueError("Missing matrix_mode parameter")
        
        mode = mode_param.value
        
        # Default to identity matrix
        M = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.warp(imagebuf, M)
        
        if result is None or result.has_error():
            raise RuntimeError("warp failed")
        
        return result
    
    def _apply_rotate(
        self,
        imagebuf: oiio.ImageBuf,
        filter: RotateFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Rotate image."""
        angle_param = filter.get_parameter("angle")
        
        if not angle_param:
            raise ValueError("Missing angle parameter")
        
        angle_str = angle_param.value
        
        # Parse angle
        if angle_str == "arbitrary":
            arb_param = filter.get_parameter("arbitrary_angle")
            if not arb_param:
                raise ValueError("Missing arbitrary_angle parameter")
            angle = arb_param.value
        else:
            angle = float(angle_str)
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.rotate(imagebuf, angle)
        
        if result is None or result.has_error():
            raise RuntimeError(f"rotate by {angle} degrees failed")
        
        return result
    
    def _apply_noise_injection(
        self,
        imagebuf: oiio.ImageBuf,
        filter: NoiseInjectionFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Inject noise into image."""
        noise_param = filter.get_parameter("noise_type")
        amount_param = filter.get_parameter("amount")
        
        if not all([noise_param, amount_param]):
            raise ValueError("Missing noise parameters")
        
        noise_type = noise_param.value if noise_param else None
        amount = amount_param.value if amount_param else None
        
        if noise_type is None or amount is None:
            raise ValueError("Noise parameters have no value")
        
        result = oiio.ImageBuf()
        # Note: OIIO noise function may have different signature
        # Using a simpler approach with add/mul for now
        success = True  # Placeholder - would need OIIO API verification
        
        if not success:
            raise RuntimeError(f"noise injection ({noise_type}) failed")
        
        return result if success else imagebuf
    
    def _apply_dilate(
        self,
        imagebuf: oiio.ImageBuf,
        filter: DilateFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply dilation (morphological operation)."""
        width_param = filter.get_parameter("kernel_width")
        height_param = filter.get_parameter("kernel_height")
        
        if not all([width_param, height_param]):
            raise ValueError("Missing kernel parameters")
        
        width = width_param.value if width_param else 0
        height = height_param.value if height_param else 0
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.dilate(imagebuf, width, height)
        
        if result is None or result.has_error():
            raise RuntimeError("dilate failed")
        
        return result
    
    def _apply_erode(
        self,
        imagebuf: oiio.ImageBuf,
        filter: ErodeFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Apply erosion (morphological operation)."""
        width_param = filter.get_parameter("kernel_width")
        height_param = filter.get_parameter("kernel_height")
        
        if not all([width_param, height_param]):
            raise ValueError("Missing kernel parameters")
        
        width = width_param.value if width_param else 0
        height = height_param.value if height_param else 0
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.erode(imagebuf, width, height)
        
        if result is None or result.has_error():
            raise RuntimeError("erode failed")
        
        return result
    
    def _apply_channel_extract(
        self,
        imagebuf: oiio.ImageBuf,
        filter: ChannelExtractFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Extract and reorder specific channels."""
        channels_param = filter.get_parameter("channels")
        
        if not channels_param:
            raise ValueError("Missing channels parameter")
        
        channels_str = channels_param.value
        channel_list = tuple(ch.strip() for ch in channels_str.split(","))
        
        # OIIO 2.0+ API: returns result directly
        result = oiio.ImageBufAlgo.channels(imagebuf, channel_list)
        
        if result is None or result.has_error():
            raise RuntimeError(f"channel extraction ({channels_str}) failed")
        
        return result
    
    def _apply_channel_invert(
        self,
        imagebuf: oiio.ImageBuf,
        filter: ChannelInvertFilter,
        roi: Optional[oiio.ROI] = None
    ) -> oiio.ImageBuf:
        """Invert pixel values (1 - value) per channel."""
        channels_param = filter.get_parameter("channels")
        
        # OIIO 2.0+ API: returns result directly
        # If channels is empty, invert all
        result = oiio.ImageBufAlgo.invert(imagebuf)
        
        if result is None or result.has_error():
            raise RuntimeError("channel invert failed")
        
        return result
