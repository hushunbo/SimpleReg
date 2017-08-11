# \file ITK.py
# \brief Basis class for ITK-based registration tools
#
# \author     Michael Ebner (michael.ebner.14@ucl.ac.uk)
# \date       Aug 2017

# Import libraries
import os
import sys
import itk
import SimpleITK as sitk

# Import modules from src-folder
import pythonhelper.PythonHelper as ph
import pythonhelper.SimpleITKHelper as sitkh


class WrapItkRegistration(object):

    def __init__(
        self,
        fixed_itk,
        moving_itk,
        dimension,
        pixel_type=itk.D,
        fixed_itk_mask=None,
        moving_itk_mask=None,
        registration_type="Rigid",
        metric="Correlation",
        interpolator="Linear",
        initializer_type=None,
        optimizer="RegularStepGradientDescent",
        use_multiresolution_framework=False,
        shrink_factors=[2, 1],
        smoothing_sigmas=[1, 0],
        verbose=1,
        itk_oriented_gaussian_interpolate_image_filter=None,
        optimizer_scales=None,
        # optimizer_scales="PhysicalShift",
        # optimizer="ConjugateGradientLineSearch",
        # metric_params=None,source
        # optimizer_params={
        #     'learningRate': 1,
        #     'numberOfIterations': 100,
        # },
        # # optimizer="RegularStepGradientDescent",
        # # optimizer_params={
        # #     'learningRate': 1,
        # #     'minStep': 1e-6,
        # #     'numberOfIterations': 200,
        # #     'gradientMagnitudeTolerance': 1e-6,
        # # },
    ):
        self._fixed_itk = fixed_itk
        self._fixed_itk_mask = fixed_itk_mask
        self._moving_itk = moving_itk
        self._moving_itk_mask = moving_itk_mask
        self._dimension = dimension
        self._pixel_type = pixel_type
        self._image_type = itk.Image[self._pixel_type, self._dimension]
        self._registration_type = registration_type
        self._metric = metric
        self._interpolator = interpolator
        self._initializer_type = initializer_type
        self._optimizer = optimizer
        self._use_multiresolution_framework = use_multiresolution_framework
        self._shrink_factors = shrink_factors
        self._smoothing_sigmas = smoothing_sigmas
        self._verbose = verbose
        self._optimizer_scales = optimizer_scales
        self._itk_oriented_gaussian_interpolate_image_filter = \
            itk_oriented_gaussian_interpolate_image_filter

        self._registration_transform_itk = None
        self._computational_time = ph.get_zero_time()

        self._mask_caster = itk.CastImageFilter[
            self._image_type, itk.Image[itk.UC, self._dimension]].New()

    ##
    # Gets the computational time it took to perform the registration
    # \date       2017-08-08 16:59:45+0100
    #
    # \param      self  The object
    #
    # \return     The computational time.
    #
    def get_computational_time(self):
        return self._computational_time

    ##
    # Gets the obtained registration transform.
    # \date       2017-08-08 16:52:36+0100
    #
    # \param      self  The object
    #
    # \return     The registration transform as sitk object.
    #
    def get_registration_transform_sitk(self):
        if self._registration_transform_sitk is None:
            raise UnboundLocalError("Execute 'run' first.")

        return self._registration_transform_sitk

    ##
    # Gets the obtained registration transform.
    # \date       2017-08-08 16:52:36+0100
    #
    # \param      self  The object
    #
    # \return     The registration transform as itk object.
    #
    def get_registration_transform_itk(self):
        if self._registration_transform_itk is None:
            raise UnboundLocalError("Execute 'run' first.")

        return self._registration_transform_itk

    ##
    # Run the registration method
    # \date       2017-08-08 17:01:01+0100
    #
    # \param      self  The object
    #
    def run(self):

        if not isinstance(self._fixed_itk, self._image_type):
            raise ValueError("Fixed image must be of type itk.Image")

        if not isinstance(self._moving_itk, self._image_type):
            raise ValueError("Moving image must be of type itk.Image")

        if self._fixed_itk_mask is not None and \
                not isinstance(self._fixed_itk_mask, self._image_type):
            raise ValueError(
                "Fixed image mask must be of type itk.Image")

        if self._moving_itk_mask is not None and \
                not isinstance(self._moving_itk_mask, self._image_type):
            raise ValueError(
                "Moving image mask must be of type itk.Image")

        time_start = ph.start_timing()

        # Execute registration method
        self._run_v3()
        # self._run_v4()

        # Get computational time
        self._computational_time = ph.stop_timing(time_start)

    def _run_v3(self):

        # ---------------------------Transform Type---------------------------
        if self._registration_type == "Rigid":
            transform_type = eval(
                "itk.Euler%dDTransform[self._pixel_type]" % (
                    self._dimension))

        elif self._registration_type == "Similarity":
            transform_type = eval(
                "itk.Similarity%dDTransform[self._pixel_type]" % (
                    self._dimension))

        elif self._registration_type == "Affine":
            transform_type = itk.AffineTransform[
                self._pixel_type, self._dimension]
        else:
            raise ValueError("Registration type '%s' not known." %
                             (self._registration_type))

        # --------------------------Interpolator Type--------------------------
        if self._itk_oriented_gaussian_interpolate_image_filter is not None:
            interpolator = self._itk_oriented_gaussian_interpolate_image_filter
        else:
            interpolator_type = \
                eval("itk.%sInterpolateImageFunction[self._image_type, "
                     "self._pixel_type]" % (self._interpolator))
            interpolator = interpolator_type.New()

        # -----------------------------Metric Type-----------------------------
        if self._metric == "Correlation":
            metric_type = itk.NormalizedCorrelationImageToImageMetric[
                self._image_type, self._image_type]
        elif self._metric == "MattesMutualInformation":
            metric_type = itk.MattesMutualInformationImageToImageMetric[
                self._image_type, self._image_type]
            interpolator.SetInputImage(self._moving_itk)
        elif self._metric == "MeanSquares":
            metric_type = itk.MeanSquaresImageToImageMetric[
                self._image_type, self._image_type]

        # ---------------------------Optimizer Type---------------------------
        if self._optimizer == "RegularStepGradientDescent":
            optimizer_type = itk.RegularStepGradientDescentOptimizer
        else:
            raise ValueError(
                "For 'ImageRegistrationMethod' only "
                "RegularStepGradientDescent")

        # -----------------------Image Registration Type-----------------------
        registration_type = itk.ImageRegistrationMethod[
            self._image_type, self._image_type]

        # ----------------------------Set variables----------------------------
        registration = registration_type.New()
        registration.SetFixedImage(self._fixed_itk)
        registration.SetMovingImage(self._moving_itk)
        registration.SetInterpolator(interpolator)

        optimizer = optimizer_type.New()
        optimizer.SetGradientMagnitudeTolerance(1e-6)
        optimizer.SetMinimumStepLength(1e-6)
        optimizer.SetNumberOfIterations(200)
        optimizer.SetRelaxationFactor(0.5)
        if self._optimizer_scales is not None:
            raise ValueError("No scales allowed for 'ImageRegistrationMethod'")

        registration.SetOptimizer(optimizer)

        metric = metric_type.New()
        if self._moving_itk_mask is not None:
            self._mask_caster.SetInput(self._moving_itk_mask)
            self._mask_caster.Update()

            moving_itk_mask = self._mask_caster.GetOutput()
            moving_itk_mask.DisconnectPipeline()

            moving_mask_object = itk.ImageMaskSpatialObject[
                self._dimension].New()
            moving_mask_object.SetImage(moving_itk_mask)
            metric.SetMovingImageMask(moving_mask_object)
        if self._fixed_itk_mask is not None:
            self._mask_caster.SetInput(self._fixed_itk_mask)
            self._mask_caster.Update()

            fixed_itk_mask = self._mask_caster.GetOutput()
            fixed_itk_mask.DisconnectPipeline()

            fixed_mask_object = itk.ImageMaskSpatialObject[
                self._dimension].New()
            fixed_mask_object.SetImage(fixed_itk_mask)
            metric.SetFixedImageMask(fixed_mask_object)
        registration.SetMetric(metric)

        initial_transform = transform_type.New()
        registration.SetTransform(initial_transform)
        if self._initializer_type is not None:
            if self._dimension == 2:
                transform_which_works = itk.CenteredRigid2DTransform[
                    self._pixel_type]
            else:
                transform_which_works = itk.VersorRigid3DTransform[
                    self._pixel_type]
            initial_transform_ = transform_which_works.New()
            initializer = itk.CenteredTransformInitializer[
                transform_which_works,
                self._image_type,
                self._image_type].New()
            initializer.SetTransform(initial_transform_)
            initializer.SetFixedImage(self._fixed_itk)
            initializer.SetMovingImage(self._moving_itk)
            if self._initializer_type == "MOMENTS":
                initializer.MomentsOn()
            else:
                initializer.GeometryOn()
            initializer.InitializeTransform()
            initial_transform.SetMatrix(
                initial_transform_.GetMatrix())
            initial_transform.SetTranslation(
                initial_transform_.GetTranslation())
            initial_transform.SetCenter(
                initial_transform_.GetCenter())
        # print(initial_transform)
        registration.SetInitialTransformParameters(
            initial_transform.GetParameters())

        # Optional multi-resolution framework
        if self._use_multiresolution_framework:
            raise ValueError(
                "Multiresolution-Framework cannot be used with "
                "ImageRegistrationMethod. ImageRegistrationMethodv4 required.")

        # Execute registration
        registration.Update()

        self._registration_transform_itk = registration.GetTransform()

        if self._verbose:
            ph.print_info("Registration: WrapITK")
            ph.print_info("Transform Model: %s"
                          % (self._registration_type))
            ph.print_info("Interpolator: %s"
                          % (self._interpolator))
            ph.print_info("Metric: %s" % (self._metric))
            ph.print_info("CenteredTransformInitializer: %s"
                          % (self._initializer_type))
            ph.print_info("Optimizer: %s"
                          % (self._optimizer))
            ph.print_info("Use Multiresolution Framework: %s"
                          % (self._use_multiresolution_framework),
                          newline=not self._use_multiresolution_framework)
            if self._use_multiresolution_framework:
                print(
                    " (" +
                    "shrink factors = " + str(self._shrink_factors) +
                    ", " +
                    "smoothing sigmas = " + str(self._smoothing_sigmas) +
                    ")"
                )
            ph.print_info("Use Fixed Mask: %s"
                          % (self._fixed_itk_mask is not None))
            ph.print_info("Use Moving Mask: %s"
                          % (self._moving_itk_mask is not None))

        self._registration_transform_sitk = \
            sitkh.get_sitk_from_itk_transform(self._registration_transform_itk)

        if self._verbose:
            ph.print_info("Summary Registration Method Result:")
            ph.print_info("\tOptimizer\'s stopping condition: %s" % (
                registration.GetOptimizer().GetStopConditionDescription()))
            ph.print_info("\tFinal metric value: %s" % (
                optimizer.GetValue()))

            sitkh.print_sitk_transform(self._registration_transform_sitk)

    def _run_v4(self):

        # -----------------Define used types for registration-----------------
        if self._registration_type == "Rigid":
            transform_type = eval(
                "itk.Euler%dDTransform[self._pixel_type]" % (
                    self._dimension))

        # elif self._registration_type == "Similarity":
        #     transform_type = eval(
        #         "itk.Similarity%dDTransform[self._pixel_type]" % (
        #             self._dimension))

        elif self._registration_type == "Affine":
            transform_type = itk.AffineTransform[
                self._pixel_type, self._dimension]
        else:
            raise ValueError("Registration type '%s' not known." %
                             (self._registration_type))

        interpolator_type = \
            eval("itk.%sInterpolateImageFunction[self._image_type, "
                 "self._pixel_type]" % (self._interpolator))

        optimizer_type = itk.RegularStepGradientDescentOptimizerv4[
            self._pixel_type]

        metric_type = itk.MattesMutualInformationImageToImageMetricv4[
            self._image_type, self._image_type]

        registration_type = itk.ImageRegistrationMethodv4[
            self._image_type, self._image_type]

        optimizer = optimizer_type.New()
        optimizer.SetMinimumStepLength(1e-6)
        optimizer.SetNumberOfIterations(200)
        optimizer.SetGradientMagnitudeTolerance(1e-6)
        optimizer.SetRelaxationFactor(0.5)
        # optimizer.SetLearningRate(1)
        # optimizer.SetMaximumStepLength(1.00)
        # optimizer = itk.ConjugateGradientLineSearchOptimizer.New()
        # optimizer.SetNumberOfIterations(100)
        # registration.SetOptimizer(optimizer)
        # Set the optimizer to sample the metric at regular steps
        # registration.SetOptimizerAsExhaustive(numberOfSteps=50,
        # stepLength=1.0)

        metric = metric_type.New()
        metric.SetFixedInterpolator(interpolator_type.New())
        metric.SetMovingInterpolator(interpolator_type.New())

        initial_transform = transform_type.New()
        if self._initializer_type is not None:
            if self._dimension == 2:
                transform_which_works = itk.CenteredRigid2DTransform[
                    self._pixel_type]
            else:
                transform_which_works = itk.VersorRigid3DTransform[
                    self._pixel_type]
            initial_transform_ = transform_which_works.New()
            initializer = itk.CenteredTransformInitializer[
                transform_which_works,
                self._image_type,
                self._image_type].New()
            initializer.SetTransform(initial_transform_)
            initializer.SetFixedImage(self._fixed_itk)
            initializer.SetMovingImage(self._moving_itk)
            if self._initializer_type == "MOMENTS":
                initializer.MomentsOn()
            else:
                initializer.GeometryOn()
            initializer.InitializeTransform()
            initial_transform.SetMatrix(
                initial_transform_.GetMatrix())
            initial_transform.SetTranslation(
                initial_transform_.GetTranslation())
            initial_transform.SetCenter(
                initial_transform_.GetCenter())

        registration = registration_type.New()
        registration.SetFixedImage(self._fixed_itk)
        registration.SetMovingImage(self._moving_itk)
        registration.SetMovingInitialTransform(initial_transform)
        registration.SetFixedInitialTransform(transform_type.New())
        registration.SetOptimizer(optimizer)
        # registration.SetInitialTransformParameters(
        #     initial_transform.GetParameters())

        # if self._metric == "Correlation":
        #     # metric = itk.NormalizedCorrelationImageToImageMetric[
        #     #     self._image_type, self._image_type].New()
        #     metric = itk.MattesMutualInformationImageToImageMetricv4[
        #         self._image_type, self._image_type].New()
        # elif self._metric == "MattesMutualInformation":
        #     metric = itk.MattesMutualInformationImageToImageMetricv4[
        #         self._image_type, self._image_type].New()
        # elif self._metric == "MeanSquares":
        #     metric = itk.MeanSquaresImageToImageMetricv4[
        #         self._image_type, self._image_type].New()
        # metric = itk.MattesMutualInformationImageToImageMetric[image_type, image_type].New()
        # metric.SetNumberOfHistogramBins(200)

        if self._moving_itk_mask is not None:
            self._mask_caster.SetInput(self._moving_itk_mask)
            self._mask_caster.Update()

            moving_itk_mask = self._mask_caster.GetOutput()
            moving_itk_mask.DisconnectPipeline()

            moving_mask_object = itk.ImageMaskSpatialObject[
                self._dimension].New()
            moving_mask_object.SetImage(moving_itk_mask)
            metric.SetMovingImageMask(moving_mask_object)

        if self._fixed_itk_mask is not None:
            self._mask_caster.SetInput(self._fixed_itk_mask)
            self._mask_caster.Update()

            fixed_itk_mask = self._mask_caster.GetOutput()
            fixed_itk_mask.DisconnectPipeline()

            fixed_mask_object = itk.ImageMaskSpatialObject[
                self._dimension].New()
            fixed_mask_object.SetImage(fixed_itk_mask)
            metric.SetFixedImageMask(fixed_mask_object)
        registration.SetMetric(metric)

        # # Optional multi-resolution framework
        # if self._use_multiresolution_framework:
        #     # Set the shrink factors for each level where each level has the
        #     # same shrink factor for each dimension
        #     registration.SetShrinkFactorsPerLevel(
        #         self._shrink_factors)

        #     # Set the sigmas of Gaussian used for smoothing at each level
        #     registration.SetSmoothingSigmasPerLevel(
        #         self._smoothing_sigmas)

        #     # Enable the smoothing sigmas for each level in physical units
        #     # (default) or in terms of voxels (then *UnitsOff instead)
        #     registration.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

        # Execute registration
        registration.Update()

        self._registration_transform_itk = registration.GetTransform()
        # self._registration_transform_itk = None

        # # Estimating scales of transform parameters a step sizes, from the
        # # maximum voxel shift in physical space caused by a parameter change
        # eval("registration.SetOptimizerScalesFrom" +
        #      self._optimizer_scales)()

        if self._verbose:
            ph.print_info("Registration: WrapITK")
            ph.print_info("Transform Model: %s"
                          % (self._registration_type))
            ph.print_info("Interpolator: %s"
                          % (self._interpolator))
            ph.print_info("Metric: %s" % (self._metric))
            ph.print_info("CenteredTransformInitializer: %s"
                          % (self._initializer_type))
            ph.print_info("Optimizer: %s"
                          % (self._optimizer))
            ph.print_info("Use Multiresolution Framework: %s"
                          % (self._use_multiresolution_framework),
                          newline=not self._use_multiresolution_framework)
            if self._use_multiresolution_framework:
                print(
                    " (" +
                    "shrink factors = " + str(self._shrink_factors) +
                    ", " +
                    "smoothing sigmas = " + str(self._smoothing_sigmas) +
                    ")"
                )
            ph.print_info("Use Fixed Mask: %s"
                          % (self._fixed_itk_mask is not None))
            ph.print_info("Use Moving Mask: %s"
                          % (self._moving_itk_mask is not None))

        # except RuntimeError as err:
        #     print(err.message)
        #     # Debug:
        #     # itkh.show_itk_image(
        #     #     [self._fixed_itk, self._moving_itk],
        #     #     segmentation=self._fixed_itk_mask)

        #     print("WARNING: SetMetricAsCorrelation")
        #     registration.SetMetricAsCorrelation()
        #     registration_transform_itk = registration.Execute(
        #         self._fixed_itk, self._moving_itk)

        self._registration_transform_sitk = \
            sitkh.get_sitk_from_itk_transform(self._registration_transform_itk)

        if self._verbose:
            # ph.print_info("SimpleITK Image Registration Method:")
            # ph.print_info('\tFinal metric value: {0}'.format(
            #     registration.GetMetricValue()))
            # ph.print_info('\tOptimizer\'s stopping condition, {0}'.format(
            #     registration.GetOptimizerStopConditionDescription()))

            sitkh.print_sitk_transform(self._registration_transform_sitk)
