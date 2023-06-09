import sys
import numpy as np
# Pinocchio
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
# Meshcat
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
import meshcat_shapes

# Paths to urdf
default_urdf_path = "/home/ros/devel/RoboDemos/ROS2_packages/panda2_description/urdf/panda2_inertias_poleholder.urdf"
mesh_path = "/home/ros/devel/RoboDemos/ROS2_packages/panda2_description/panda/meshes"

# Build from URDF
model, collision_model, visual_model = pin.buildModelsFromUrdf(
    default_urdf_path, mesh_path, pin.JointModelFreeFlyer()
)
 
viz = MeshcatVisualizer(model, collision_model, visual_model)

try:
    viz.initViewer(open=True)
except ImportError as err:
    print(
        "Error while initializing the viewer. It seems you should install Python meshcat"
    )
    print(err)
    sys.exit(0)

viz.loadViewerModel()

data = viz.data

# create dictionary: joint name -> q index
joint_indices_dict = {}
for name, jnt in zip(model.names, model.joints):
    joint_indices_dict[name] = jnt.idx_q

q = pin.neutral(model)

tbl_header = ['panda_joint1', 'panda_joint2', 'panda_joint3', 'panda_joint4', 'panda_joint5', 'panda_joint6', 'panda_joint7']
q2 = [0.0,-0.7853981633974483,0.0,-2.356194490192345,0.0,1.5707963267948966,0.7853981633974483]

for fname, fvalue in zip(tbl_header, q2):
    q[joint_indices_dict[fname]] = fvalue

viz.display(q)
pin.forwardKinematics(model, viz.data, q)
pin.updateFramePlacements(model, viz.data)

# Display Visuals or Collision
DISPLAY_VISUALS = True
DISPLAY_COLLISIONS = False
# viz.displayCollisions(DISPLAY_COLLISIONS)
viz.displayVisuals(DISPLAY_VISUALS)


for frame, oMf in zip(model.frames, data.oMf):
    print(frame.name)
    if "link" in frame.name and "_sc" not in frame.name:
        meshcat_shapes.textarea(viz.viewer[frame.name]["name"], f"{frame.name}", font_size=10)
        meshcat_shapes.frame(viz.viewer[frame.name]["frame"],axis_length=0.2, axis_thickness=0.01, opacity=0.8, origin_radius=0.02)
        t_matrix_name = tf.translation_matrix(oMf.translation + np.array([0, -0.25, 0]))
        t_matrix_frame = tf.translation_matrix(oMf.translation)
        r_matrix_frame = oMf.rotation
        t_matrix_frame[0:3, 0:3] = r_matrix_frame
        viz.viewer[frame.name]["name"].set_transform(t_matrix_name)
        viz.viewer[frame.name]["frame"].set_transform(t_matrix_frame)

while True:
    viz.display(q)