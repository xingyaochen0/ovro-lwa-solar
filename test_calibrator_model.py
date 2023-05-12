from generate_calibrator_model import model_generation


msfile='/data07/msurajit/82MHz/20230309_191023_82MHz.ms'

md=model_generation(vis=msfile,pol='I',separate_pol=False)
md.calfilepath='/data07/msurajit/ovro-lwa-solar2/defaults/'

#md.gen_model_file()
md.gen_model_cl()

