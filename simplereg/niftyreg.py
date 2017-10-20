# \file NiftyReg.py
# \brief      This class makes NiftyReg accessible via Python
#
# \author     Michael Ebner (michael.ebner.14@ucl.ac.uk)
# \date       Aug 2017

# Import libraries
import os
import numpy as np
import SimpleITK as sitk
from abc import ABCMeta, abstractmethod
import nipype.interfaces.niftyreg

import pysitk.python_helper as ph
import pysitk.simple_itk_helper as sitkh

from simplereg.definitions import DIR_TMP
from simplereg.wrapper_registration import WrapperRegistration


class NiftyReg(WrapperRegistration):
    __metaclass__ = ABCMeta

    def __init__(self,
                 fixed_sitk,
                 moving_sitk,
                 fixed_sitk_mask,
                 moving_sitk_mask,
                 options,
                 omp_cores,
                 subfolder):

        WrapperRegistration.__init__(self,
                                     fixed_sitk=fixed_sitk,
                                     moving_sitk=moving_sitk,
                                     fixed_sitk_mask=fixed_sitk_mask,
                                     moving_sitk_mask=moving_sitk_mask,
                                     options=options,
                                     )

        # Subfolder within DIR_TMP where results will be stored temporarily
        self._dir_tmp = os.path.join(DIR_TMP, subfolder)

        self._fixed_str = os.path.join(self._dir_tmp, "fixed.nii.gz")
        self._moving_str = os.path.join(self._dir_tmp, "moving.nii.gz")
        self._warped_moving_str = os.path.join(
            self._dir_tmp, "warped_moving.nii.gz")

        self._fixed_mask_str = os.path.join(
            self._dir_tmp, "fixed_mask.nii.gz")
        self._moving_mask_str = os.path.join(
            self._dir_tmp, "moving_mask.nii.gz")
        self._warped_moving_mask_str = os.path.join(
            self._dir_tmp, "warped_mask.nii.gz")

        self._omp_cores = omp_cores

    def _run(self):

        # Create and delete all possibly existing files in the directory
        ph.create_directory(self._dir_tmp, delete_files=True)

        sitk.WriteImage(self._fixed_sitk, self._fixed_str)
        sitk.WriteImage(self._moving_sitk, self._moving_str)

        if self._fixed_sitk_mask is not None:
            sitk.WriteImage(self._fixed_sitk_mask, self._fixed_mask_str)

        if self._moving_sitk_mask is not None:
            sitk.WriteImage(self._moving_sitk_mask, self._moving_mask_str)


class RegAladin(NiftyReg):

    def __init__(self,
                 fixed_sitk=None,
                 moving_sitk=None,
                 fixed_sitk_mask=None,
                 moving_sitk_mask=None,
                 options="",
                 subfolder="RegAladin",
                 omp_cores=8,
                 ):

        NiftyReg.__init__(self,
                          fixed_sitk=fixed_sitk,
                          moving_sitk=moving_sitk,
                          fixed_sitk_mask=fixed_sitk_mask,
                          moving_sitk_mask=moving_sitk_mask,
                          options=options,
                          subfolder=subfolder,
                          omp_cores=omp_cores,
                          )

        self._registration_transform_str = os.path.join(
            self._dir_tmp, "registration_transform.txt")

    def _run(self, debug=0):

        super(RegAladin, self)._run()

        nreg = nipype.interfaces.niftyreg.RegAladin()
        nreg.inputs.ref_file = self._fixed_str
        nreg.inputs.flo_file = self._moving_str
        nreg.inputs.res_file = self._warped_moving_str
        nreg.inputs.aff_file = self._registration_transform_str
        nreg.inputs.omp_core_val = self._omp_cores
        nreg.inputs.args = self._options

        if self._fixed_sitk_mask is not None:
            nreg.inputs.rmask_file = self._fixed_mask_str

        if self._moving_sitk_mask is not None:
            nreg.inputs.fmask_file = self._moving_mask_str

        # Execute registration
        if debug:
            print(nreg.cmdline)
        nreg.run()

        # Read warped image
        self._warped_moving_sitk = sitk.ReadImage(self._warped_moving_str)

        # Convert to sitk affine transform
        self._registration_transform_sitk = self._convert_to_sitk_transform()

    ##
    # Convert RegAladin transform to sitk object
    #
    # Note, not tested for 2D
    # \date       2017-08-08 18:41:40+0100
    #
    # \param      self     The object
    #
    # \return     Registration transform as sitk object
    #
    def _convert_to_sitk_transform(self):

        dimension = self._fixed_sitk.GetDimension()

        # Read trafo and invert such that format fits within SimpleITK
        # structure
        matrix = np.loadtxt(self._registration_transform_str)
        A = matrix[0:dimension, 0:dimension]
        t = matrix[0:dimension, -1]

        # Convert to SimpleITK physical coordinate system
        R = np.eye(dimension)
        R[0, 0] = -1
        R[1, 1] = -1
        A = R.dot(A).dot(R)
        t = R.dot(t)

        registration_transform_sitk = sitk.AffineTransform(A.flatten(), t)

        return registration_transform_sitk

    def _get_transformed_fixed_sitk(self):
        return sitkh.get_transformed_sitk_image(
            self._fixed_sitk, self.get_registration_transform_sitk())

    def _get_transformed_fixed_sitk_mask(self):
        return sitkh.get_transformed_sitk_image(
            self._fixed_sitk_mask, self.get_registration_transform_sitk())

    def _get_warped_moving_sitk(self):
        return self._warped_moving_sitk

    def _get_warped_moving_sitk_mask(self):

        warped_moving_sitk_mask = sitk.Resample(
            self._moving_sitk_mask,
            self._fixed_sitk,
            self.get_registration_transform_sitk(),
            sitk.sitkNearestNeighbor,
            0,
            self._moving_sitk_mask.GetPixelIDValue(),
        )

        return warped_moving_sitk_mask


class RegF3D(NiftyReg):

    def __init__(self,
                 fixed_sitk=None,
                 moving_sitk=None,
                 fixed_sitk_mask=None,
                 moving_sitk_mask=None,
                 options="",
                 subfolder="RegF3D",
                 omp_cores=8,
                 ):

        NiftyReg.__init__(self,
                          fixed_sitk=fixed_sitk,
                          moving_sitk=moving_sitk,
                          fixed_sitk_mask=fixed_sitk_mask,
                          moving_sitk_mask=moving_sitk_mask,
                          options=options,
                          subfolder=subfolder,
                          omp_cores=omp_cores,
                          )

        self._registration_control_point_grid_str = os.path.join(
            self._dir_tmp, "registration_cpp.nii.gz")

    def _run(self, debug=0):

        super(RegF3D, self)._run()

        nreg = nipype.interfaces.niftyreg.RegF3D()
        nreg.inputs.ref_file = self._fixed_str
        nreg.inputs.flo_file = self._moving_str
        nreg.inputs.res_file = self._warped_moving_str
        nreg.inputs.cpp_file = self._registration_control_point_grid_str
        nreg.inputs.omp_core_val = self._omp_cores
        nreg.inputs.args = self._options

        if self._fixed_sitk_mask is not None:
            nreg.inputs.rmask_file = self._fixed_mask_str

        if self._moving_sitk_mask is not None:
            nreg.inputs.fmask_file = self._moving_mask_str

        # Execute registration
        if debug:
            print(nreg.cmdline)
        nreg.run()

        # Read warped image
        self._warped_moving_sitk = sitk.ReadImage(self._warped_moving_str)

        # Has not been used. Thus, not tested!
        self._registration_transform_sitk = sitk.ReadImage(
            self._registration_control_point_grid_str)

    def _get_transformed_fixed_sitk(self):
        raise UnboundLocalError("Not implemented for RegF3D")
        # registration_transform_inv_sitk = self._get_inverted_transform(
        #     self._registration_transform_sitk, input_moving_sitk)
        # return self._get_transformed_image_sitk()

    def _get_transformed_fixed_sitk_mask(self):
        raise UnboundLocalError("Not implemented for RegF3D")

    def _get_warped_moving_sitk(self):
        return self._warped_moving_sitk

    def _get_warped_moving_sitk_mask(self, debug=0):

        warped_moving_sitk_mask = self.get_deformed_image_sitk(
            fixed_sitk=self._fixed_sitk,
            moving_sitk=self._moving_sitk_mask,
            interpolation_order=0)

        return warped_moving_sitk_mask

    ##
    # Gets the deformed image given the obtained deformable registration
    # transform.
    # \date       2017-08-09 16:57:39+0100
    #
    # \param      self                 The object
    # \param      fixed_sitk           Fixed image as sitk.Image
    # \param      moving_sitk          Moving image as sitk.Image
    # \param      interpolation_order  Interpolation order, integer
    # \param      debug                The debug
    #
    # \return     The deformed image sitk.
    #
    def get_deformed_image_sitk(self, fixed_sitk, moving_sitk,
                                interpolation_order, debug=1):

        # REMARK:
        # Not possible to write registration transform that way since
        # some header information gets lost! Therefore, read again the one
        # which was the output of NiftyReg (and hope that file is not been
        # deleted)
        # Create and delete all possibly existing files in the directory
        # ph.create_directory(self._dir_tmp, delete_files=True)
        # sitk.WriteImage(self.get_registration_transform_sitk(),
        #                 self._registration_control_point_grid_str)

        sitk.WriteImage(fixed_sitk, self._fixed_str)
        sitk.WriteImage(moving_sitk, self._moving_str)

        nreg = nipype.interfaces.niftyreg.RegResample()
        nreg.inputs.ref_file = self._fixed_str
        nreg.inputs.flo_file = self._moving_str
        nreg.inputs.trans_file = self._registration_control_point_grid_str
        nreg.inputs.res_file = self._warped_moving_str
        nreg.inputs.omp_core_val = self._omp_cores
        nreg.inputs.args = "-inter " + str(interpolation_order)

        # Execute registration
        if debug:
            print(nreg.cmdline)
        nreg.run()

        return sitk.ReadImage(self._warped_moving_str,
                              moving_sitk.GetPixelIDValue())

    # def _get_inverted_transform(self,
    #                             input_def_field_sitk,
    #                             input_moving_sitk,
    #                             debug=0,
    #                             endl=" \\\n"):

    #     filename_1 = os.path.join(self._dir_tmp, "filename_1.nii.gz")
    #     filename_2 = os.path.join(self._dir_tmp, "filename_2.nii.gz")
    #     filename_3 = os.path.join(self._dir_tmp, "filename_3.nii.gz")

    #     sitk.WriteImage(input_def_field_sitk, filename_1)
    #     sitk.WriteImage(input_moving_sitk, filename_2)

    #     cmd = REG_TRANSFORM_EXE + " -invNrr" + endl
    #     cmd += filename_1 + endl
    #     cmd += filename_2 + endl
    #     cmd += filename_3 + endl

    #     # Execute registration
    #     ph.execute_command(cmd, verbose=debug)

    #     return sitk.ReadImage(filename_3)

    # def _get_transformed_image_sitk(self,
    #                                moving_sitk,
    #                                fixed_sitk,
    #                                deformation_field,
    #                                debug=0,
    #                                endl=" \\\n"):
