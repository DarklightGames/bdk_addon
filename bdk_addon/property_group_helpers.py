from bpy.props import BoolProperty, EnumProperty, FloatProperty


class CurveModifierMixin:
    use_curve_modifiers: BoolProperty(name='Use Curve Modifiers', default=False)
    is_curve_reversed: BoolProperty(name='Reverse Curve', default=False)  # TODO: Rename to curve_is_reversed
    curve_trim_mode: EnumProperty(name='Trim Mode', items=(('NONE', 'None', '', 0), ('FACTOR', 'Factor', '', 1),('LENGTH', 'Distance', '', 2),), default='NONE')
    curve_trim_factor_start: FloatProperty(name='Trim Factor Start', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    curve_trim_factor_end: FloatProperty(name='Trim Factor End', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    curve_trim_length_start: FloatProperty(name='Trim Length Start', default=0.0, min=0.0, subtype='DISTANCE')
    curve_trim_length_end: FloatProperty(name='Trim Length End', default=0.0, min=0.0, subtype='DISTANCE')
    curve_normal_offset: FloatProperty(name='Normal Offset', default=0.0, subtype='DISTANCE')
    curve_align_to_tangent: BoolProperty(name='Align to Tangent', default=False, description='Align the X axis of the object to the tangent of the curve')
