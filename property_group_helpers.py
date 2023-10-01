from bpy.props import BoolProperty, EnumProperty, FloatProperty


def add_curve_modifier_properties(cls):
    # Add the curve modifier properties to the type annotation of the given class.
    cls.__annotations__['is_curve_reversed'] = BoolProperty(name='Reverse Curve', default=False)  # TODO: Rename to curve_is_reversed
    cls.__annotations__['curve_trim_mode'] = EnumProperty(name='Trim Mode', items=(('FACTOR', 'Factor', '', 0),('LENGTH', 'Distance', '', 1),), default='FACTOR')
    cls.__annotations__['curve_trim_factor_start'] = FloatProperty(name='Trim Factor Start', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    cls.__annotations__['curve_trim_factor_end'] = FloatProperty(name='Trim Factor End', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    cls.__annotations__['curve_trim_length_start'] = FloatProperty(name='Trim Length Start', default=0.0, min=0.0, subtype='DISTANCE')
    cls.__annotations__['curve_trim_length_end'] = FloatProperty(name='Trim Length End', default=0.0, min=0.0, subtype='DISTANCE')
    cls.__annotations__['curve_normal_offset'] = FloatProperty(name='Normal Offset', default=0.0, subtype='DISTANCE')
    cls.__annotations__['curve_align_to_tangent'] = BoolProperty(name='Align to Tangent', default=False, description='Align the X axis of the object to the tangent of the curve')
