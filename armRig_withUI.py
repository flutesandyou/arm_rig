import pymel.core as pm
import sys
class ArmRigUI(object):
    def __init__(self):
        self.window_name = "ArmRig_Tool"
        self.arm_joints = []
        self.roll_joints = []
        self.arm_joints_field = None
        self.roll_joints_field = None

    def create_ui(self):
        if pm.window(self.window_name, exists=True):
            pm.deleteUI(self.window_name)

        with pm.window(self.window_name, title="Arm Rig Tool"):
            with pm.columnLayout(adjustableColumn=True, rowSpacing=5):
                pm.separator(height=5, style='none')

                # Adding the usage note                            # Adding a frame to make the usage note more noticeable
                pm.text(label="Step1: Please select joints in order Arm -> Forearm -> Hand",
                        align='center', wordWrap=True, 
                        font="boldLabelFont")  # Bold font for visibility
                    
                
                with pm.rowLayout(numberOfColumns=3, columnWidth3=(80, 150, 30), adjustableColumn=2):
                    pm.text(label="Arm Joints")
                    self.arm_joints_field = pm.textField(editable=False)
                    pm.button(label="<<", command=pm.Callback(self.select_arm_joints))
                
                pm.separator(height=5, style='double')
                # Adding the usage note                            # Adding a frame to make the usage note more noticeable
                pm.text(label="Step2: Please select Roll joints",
                        align='center', wordWrap=True, 
                        font="boldLabelFont")  # Bold font for visibility
                
                with pm.rowLayout(numberOfColumns=3, columnWidth3=(80, 150, 30), adjustableColumn=2):
                    pm.text(label="Roll Joints")
                    self.roll_joints_field = pm.textField(editable=False)
                    pm.button(label="<<", command=pm.Callback(self.select_roll_joints))
                


                pm.separator(height=10, style='double')
                pm.button(label="Build Arm Rig", command=pm.Callback(self.create_arm_rig))
                pm.button(label="Delete Arm Rig", command=pm.Callback(self.delete_arm_rig))

        pm.showWindow()

    def select_arm_joints(self):
        selection = pm.ls(selection=True, type="joint")

        if len(selection) != 3:
            pm.warning("Please select arm -> forearm -> hand")
            return
        descendants = pm.listRelatives(selection[0], allDescendents=True, type="joint") or []
        if selection[1] and selection[2] not in descendants:
            pm.warning("Please select arm -> forearm -> hand")
            return

        if len(selection) == 3:
            self.arm_joints = selection
            joint_names = ", ".join([joint.name() for joint in selection])
            self.arm_joints_field.setText(joint_names)
        else:
            pm.warning("Please select exactly 3 joints: arm -> forearm -> hand")

    def select_roll_joints(self):
        selection = pm.ls(selection=True, type="joint")
        if selection:
            self.roll_joints = selection
            # check if arm joints are part of roll joints lol!
            if bool(set(self.roll_joints) & set(self.arm_joints)):
                pm.warning("Dont select arm joints as roll joints")
                return
            joint_names = ", ".join([joint.name() for joint in selection])
            self.roll_joints_field.setText(joint_names)
        else:
            pm.warning("Please select at least one roll joint")


    def create_arm_rig(self):
        arm_joints = self.arm_joints
        roll_joints = self.roll_joints

        if len(arm_joints) != 3:
            pm.warning("Please fill all fields")
            return
        if not roll_joints:
            pm.warning("Please fill Roll joints")
            return
        
        # Make sure rig is not created yet
        if pm.ls(arm_joints[0].nodeName() + "_Rig", type='transform'):
            pm.warning("Arm Rig already exists")
            if not self.ask_rebuild_rig():
                # Stop function if user cancels
                return
            else:
                # Delete existing rig
                for joint in roll_joints:
                    delete_nodes_containing(joint.nodeName(),'multiplyDivide')
                delete_nodes_containing(arm_joints[0].nodeName() + "_Rig", 'transform')

        # Store joints for ease of read =)
        arm = arm_joints[0]
        forearm = arm_joints[1]
        hand = arm_joints[2]

        pm.select(clear=True)

        # Initialize lists for IK and FK joints
        ik_joints = []
        fk_groups = []
        fk_controls = []

        # Create FK Controls
        for j in arm_joints:
            
            null_group = pm.group(empty=True, n="FK_" + j.nodeName() + "_Offset")
            fk_groups.append(null_group)
            null_group.setMatrix(j.getMatrix(worldSpace=True), worldSpace=True)
            
            # Params for FK controls
            col = (0, 0, 1)
            thick = 2

            # Parent the null group to previous curve if not first iteration
            if j != arm_joints[0]:
                pm.parent(null_group, fk_control)
            # # Create control shape for FK
            if j == arm_joints[0]:
                fk_control = create_custom_circle(radius=14.0, sections=8, color=col, thickness=thick)
            elif j == arm_joints[1]:
                fk_control = create_custom_circle(radius=9.0, sections=8, color=col, thickness=thick)
            elif j == arm_joints[2]:
                fk_control = create_custom_circle(radius=7.0, sections=8, color=col, thickness=thick)
            
            fk_control.rename("FK_" + j.nodeName() + "_Ctrl")
            fk_controls.append(fk_control)
            # Pre rotate for correct orientation
            pm.rotate(fk_control, (0, 90, 0))
            # Freeze transformations (including rotation)
            pm.makeIdentity(fk_control, apply=True, rotate=True, normal=False)
            pm.parent(fk_control, null_group)
            # Zero out the rotations and translations
            pm.xform(fk_control, rotation=(0, 0, 0), translation=(0, 0, 0))

            # Hide & lock translate and scale attributes
            for attr in ['translateX', 'translateY', 'translateZ', 'scaleX', 'scaleY', 'scaleZ']:
                pm.setAttr(fk_control + '.' + attr, keyable=False, channelBox=False, lock=True)

        pm.select(clear=True)

        # Create IK joints
        for j in arm_joints:
            # Create a new joint
            ik_joint = pm.joint(n="IK_" + j.nodeName())
            ik_joints.append(ik_joint)
            
            # Apply joint-specific attributes
            ik_joint.setAttr('rotateOrder', j.getAttr('rotateOrder'))
            ik_joint.setAttr('jointOrient', j.getAttr('jointOrient'))  # Apply joint orientation
            ik_joint.setAttr('preferredAngle', j.getAttr('preferredAngle'))  # Apply preferred angle
            
            # Apply the world matrix to the new joint
            ik_joint.setMatrix(j.getMatrix(worldSpace=True), worldSpace=True)

        # Create an IK handle using the first and last IK joints
        ik_handle, effector = pm.ikHandle(startJoint=ik_joints[0], endEffector=ik_joints[-1], solver='ikRPsolver')
        ik_handle.rename("IK_Handle_" + arm.nodeName())

        print("IK Handle created from {} to {}".format(ik_joints[0], ik_joints[-1]))

        # Create locator for pole vector
        loc_control = create_custom_locator(name='IK_Pole_' + forearm.nodeName() + '_Ctrl', size=3.0, color=(1, 0, 0))
        loc_group = pm.group(loc_control, n="IK_Pole_" + forearm.nodeName() + "_Offset")
        loc_group.setMatrix(forearm.getMatrix(worldSpace=True), worldSpace=True)
        #shift locator a bit back
        pm.xform(loc_control, rotation=(0, 0, 0), translation=(-15, 0, -40))
        pm.makeIdentity(loc_control, apply=True, translate=True, normal=False)
        
        # Wierd stuff but it does the trick
        grp = pm.group(em=True, n="Orient_" + forearm.nodeName() + "_Grp")
        grp.setTranslation(forearm.getTranslation(worldSpace=True), worldSpace=True)
        pm.parent(grp, loc_group)
        pm.parent(loc_control, grp)
        pm.xform(loc_control, rotation=(0, 0, 0))

        # Create the pole vector constraint
        pm.poleVectorConstraint(loc_control, ik_handle)
        print("Pole vector constraint added between {} and {}".format(loc_control, ik_handle))

        # Create the NURBS cube control
        handIK_control = create_custom_cube(name="IK_" + hand.nodeName() + "_Ctrl", size=10.0, color=(1, 0.7, 0), thickness=2)
        handIK_group = pm.group(handIK_control, n="IK_" + j.nodeName() + "_Offset")
        handIK_group.setMatrix(hand.getMatrix(worldSpace=True), worldSpace=True)
        # Constrain to the IK handle and hand
        pnt_cs_handIK = pm.pointConstraint(handIK_control, ik_handle)
        pm.orientConstraint(handIK_control, ik_joints[2])
        # Hide & lock translate and rotate attributes
        for attr in ['scaleX', 'scaleY', 'scaleZ']:
            pm.setAttr(handIK_control + '.' + attr, keyable=False, channelBox=False, lock=True)
        # hide ik joints and handle
        for ik_joint in ik_joints:
            ik_joint.v.set(0)
        ik_handle.v.set(0)

        # Create IKFK switch
        switch_control = create_custom_triangle(name="IKFK_Switch_" + arm.nodeName() + "_Ctrl", size=10.0, color=(0, 1, 0), thickness=2)
        switch_group = pm.group(switch_control, n="IKFK_Switch_"  + arm.nodeName() + "_Offset")
        # Reposition the switch
        switch_group.translate.set(arm.translate.get() + (40,0,0))
        # Hide & lock translate, rotate, and scale attributes
        for attr in ['translateX', 'translateY', 'translateZ', 'rotateX', 'rotateY', 'rotateZ', 'scaleX', 'scaleY', 'scaleZ']:
            pm.setAttr(switch_control + '.' + attr, keyable=False, channelBox=False, lock=True)
        # Attr for a switch
        pm.addAttr(switch_control, longName= arm.nodeName() + '_IKFK', attributeType='float', keyable=True, defaultValue=1.0, minValue=0.0, maxValue=1.0)
        switch_attr = switch_control.attr(arm.nodeName() + '_IKFK')

        # Create groups for a rig
        rig_group = pm.group(em=True, n=arm.nodeName() + "_Rig")
        ik_group = pm.group(em=True, p=rig_group, n="IK_" + arm.nodeName() + "_Group")
        fk_group = pm.group(em=True, p=rig_group, n="FK_" + arm.nodeName() + "_Group")
        constraints_group = pm.group(em=True, p=rig_group, n="Constraints_" + arm.nodeName() + "_Group")

        pm.parent(ik_joints[0], loc_group, ik_handle, handIK_group, ik_group)
        pm.parent(fk_groups[0], fk_group)
        pm.parent(switch_group, rig_group)

        # Add constraints and driven keys for IKFK
        for index, j in enumerate(arm_joints):
            pnt_cs = pm.parentConstraint(ik_joints[index], j, mo=True)
            pnt_cs = pm.parentConstraint(fk_controls[index], j, mo=True)
            pm.parent(pnt_cs, constraints_group)
            # Set Driven Keys to drive the weights between IK and FK
            pm.setDrivenKeyframe(pnt_cs.getWeightAliasList()[0], cd=switch_attr, dv=0, v=0)  # attr 1 IK_weight = 0)
            pm.setDrivenKeyframe(pnt_cs.getWeightAliasList()[1], cd=switch_attr, dv=0, v=1)  # attr 0 FK_weight = 1)
            pm.setDrivenKeyframe(pnt_cs.getWeightAliasList()[0], cd=switch_attr, dv=1, v=1)  # attr 1 IK_weight = 1)
            pm.setDrivenKeyframe(pnt_cs.getWeightAliasList()[1], cd=switch_attr, dv=1, v=0)  # attr 0 FK_weight = 0)

            # Set driven keys for visibility control
            # When IKFK switch is 0 (FK mode), FK is visible and IK is hidden
            pm.setDrivenKeyframe(fk_controls[index].visibility, cd=switch_attr, dv=0, v=1)  # attr 0 FK visible
            pm.setDrivenKeyframe(fk_controls[index].visibility, cd=switch_attr, dv=1, v=0)  # attr 1 FK hidden
            # IK visible
        pm.setDrivenKeyframe(handIK_control.visibility, cd=switch_attr, dv=1, v=1) # attr 1 IK visible
        pm.setDrivenKeyframe(handIK_control.visibility, cd=switch_attr, dv=0, v=0) # attr 0 IK hidden
        pm.setDrivenKeyframe(loc_control.visibility, cd=switch_attr, dv=1, v=1) # attr 1 IK visible
        pm.setDrivenKeyframe(loc_control.visibility, cd=switch_attr, dv=0, v=0) # attr 0 IK hidden

        #sort roll joints cuz we don't believe in names
        sorted_roll_joints = sort_roll_joints_by_distance(roll_joints, forearm)
        num_of_joints = len(roll_joints)
        frac = generate_roll_fractions(len(roll_joints), max_value=0.75,min_value= 0.25)[::-1]
        
        for i, joint in enumerate(sorted_roll_joints):
            # Create a multiplyDivide node for each roll joint
            mult_node = pm.createNode('multiplyDivide', name= joint + '_rotationMult')
            # Set the multiply operation
            mult_node.operation.set(1)  # 1 = Multiply
            # Set the input2X to the fraction for this roll joint
            mult_node.input2X.set(frac[i])
            # Connect the driver control's rotateX to the input1X of the multiplyDivide node
            pm.connectAttr(hand + '.rotateX', mult_node + '.input1X')
            # Connect the outputX of the multiplyDivide node to the joint's rotateX
            pm.connectAttr(mult_node + '.outputX', joint + '.rotateX')

        pm.displayInfo("Arm rig was built successfully.")


    def delete_arm_rig(self):
        # Delete existing rig
        arm_joints = self.arm_joints
        roll_joints = self.roll_joints
        
        if roll_joints and arm_joints:
            if pm.ls(arm_joints[0].nodeName() + "_Rig", type='transform'):
                for joint in roll_joints:
                    delete_nodes_containing(joint.nodeName(),'multiplyDivide')
                delete_nodes_containing(arm_joints[0].nodeName() + "_Rig", 'transform')
                # except solvers actually but they can be shared among other rigs in the scene so leave them be
                pm.displayInfo("Arm Rig was deleted")
            else:
                pm.warning("Arm Rig does not exist")
        else:
            pm.warning("Please fill all fields")

    def ask_rebuild_rig(self):
        # Create a confirm dialog
        result = pm.confirmDialog(
            title='Rebuild Rig',
            message='Arm Rig already exists. Do you want to rebuild it?',
            button=['Yes', 'No'],
            defaultButton='No',
            cancelButton='No',
            dismissString='No'
        )
        # Check the user's response
        if result == 'Yes':
            pm.displayInfo("Rebuilding Arm Rig...")
            return True
        else:
            pm.displayInfo("Canceled. Arm Rig will not be rebuilt.")
            return False


# Create and show the UI
armrigtool = ArmRigUI()
armrigtool.create_ui()

# Utility standalone functions better be in separate module
def create_custom_locator(name, size=3.0, color=(1, 0, 0)):
    # Create the locator
    loc_control = pm.spaceLocator(n=name)
    
    # Get the shape node
    loc_shape = loc_control.getShape()
    
    # Set the color
    loc_shape.overrideEnabled.set(1)
    loc_shape.overrideRGBColors.set(1)
    loc_shape.overrideColorRGB.set(*color)
    
    # Change the size of the locator
    loc_shape.localScale.set([size, size, size])
    
    return loc_control
def create_custom_circle(radius=14.0, sections=8, color=(1, 0, 0), thickness=2):
    # Create the circle curve
    circle_curve = pm.circle(radius=radius, sections=sections)[0]
    # Get the shape node of the curve
    circle_shape = circle_curve.getShape()
    # Set the color
    circle_shape.overrideEnabled.set(1)
    circle_shape.overrideRGBColors.set(1)
    circle_shape.overrideColorRGB.set(color)
    # Make the curve thicker
    circle_shape.lineWidth.set(thickness)
    
    return circle_curve

def create_custom_cube(name, size=10.0, color=(1, 1, 0), thickness=2):
    # Create the NURBS cube
    nurbs_cube = pm.curve(n = name, d=1, p=[(-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5)], k=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])

    # Scale the cube
    pm.scale(nurbs_cube, [size, size, size])
    # Freeze transformations to apply the scale
    pm.makeIdentity(nurbs_cube, apply=True, t=1, r=1, s=1, n=0)
    # Set the color
    shape = nurbs_cube.getShape()
    shape.overrideEnabled.set(1)
    shape.overrideRGBColors.set(1)
    shape.overrideColorRGB.set(color)
    # Make the curve thicker
    shape.lineWidth.set(thickness)
    # Center pivot
    pm.xform(nurbs_cube, centerPivots=True)
    
    return nurbs_cube

def create_custom_triangle(name, size=10.0, color=(0, 1, 0), thickness=2):
    # Create the NURBS triangle curve with the peak at the top (+Y axis) and facing the Z-axis
    nurbs_triangle = pm.curve(n=name, d=1, 
                              p=[(0, 0, -0.577), (0.5, 0, 0.289), (-0.5, 0, 0.289), (0, 0, -0.577)],
                              k=[0, 1, 2, 3])  # Triangle points facing forward (+Z), peak at Y+
    
    pm.rotate(nurbs_triangle, (90, 0, 0), r=True)
    # Scale the triangle
    pm.scale(nurbs_triangle, [size, size, size])
    # Freeze transformations to apply the scale and rotation
    pm.makeIdentity(nurbs_triangle, apply=True, t=1, r=1, s=1, n=0)
    # Set the color
    shape = nurbs_triangle.getShape()
    shape.overrideEnabled.set(1)
    shape.overrideRGBColors.set(1)
    shape.overrideColorRGB.set(color)
    # Make the curve thicker
    shape.lineWidth.set(thickness)
    # Center pivot
    pm.xform(nurbs_triangle, centerPivots=True)
    return nurbs_triangle

def calculate_distance(obj1, obj2):
    """Calculate the distance between two objects in world space."""
    pos1 = pm.xform(obj1, q=True, ws=True, t=True)
    pos2 = pm.xform(obj2, q=True, ws=True, t=True)
    return ((pos1[0] - pos2[0])**2 + 
            (pos1[1] - pos2[1])**2 + 
            (pos1[2] - pos2[2])**2) ** 0.5

def sort_roll_joints_by_distance(roll_joints, forearm_joint):
    return sorted(roll_joints, key=lambda joint: calculate_distance(joint, forearm_joint))

def generate_roll_fractions(num_joints, max_value=0.75, min_value=0.15):
    if num_joints == 1:
        fractions = [0.5]
    else:
        step = (max_value - min_value) / (num_joints - 1)
        fractions = [max_value - i * step for i in range(num_joints)]
    return fractions

def delete_nodes_containing(substring, node_type=None):
    # Find all nodes of the specified type, or all nodes if no type is provided
    if node_type:
        nodes = pm.ls(type=node_type)
    else:
        nodes = pm.ls()

    # Iterate through the nodes and delete those that contain the substring
    for node in nodes:
        # Use the string name of the node for the substring check
        if substring in str(node.name()):
            pm.delete(node)
