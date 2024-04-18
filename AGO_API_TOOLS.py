"""
Author: Eric Millan
Updated: April 16, 2024
Description:
    Inputs:
    Process:
    Outputs:
"""

# %%************************************************************************
# IMPORTS AND CONFIG                                                      **
# **************************************************************************
import sys
import os
import arcpy, arcpy.management, arcpy.conversion, arcpy.analysis
import numpy as np
import matplotlib.pyplot as plt
import PIL
import seaborn as sns
from scipy.stats import norm
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
import geopandas as gpd
import pandas as pd
import shutil
import fiona


# import the south coast function library and the email function 
sys.path.append(r'\\spatialfiles.bcgov\work\srm\sry\Local\scripts\python')
from sc_python_function_library import * 
import email_function 
from email_function import SendEmail

# %%************************************************************************
# MAMU AGOL TOOL CLASS AND METHOD DEFINITIONS                             **
# **************************************************************************
class AGOL_SURVEY_CONNECTION:

    def __init__(self, item_id, field_list):
        
        """
        This Class initaties a GIS API Call to access a specific feature. It makes
        use of the South Coast Code Library for credentials, and the only required 
        input is for an AGOL Item ID.

        In this constructor, Most validation occurs. Following Conditions Must be 
        met for an AGOL ITEM ID:
        1. 

        General Structure is:

        gis --> agol_item --> feature_layer
        """

        print("INITIALIZING AGOL CONNECTION")
        try:
            self.item_id = item_id
            self.url = 'https://governmentofbc.maps.arcgis.com'
            self.agol_username, self.agol_password = get_credentials("agol")
            self.gis = GIS(self.url, self.agol_username, self.agol_password, verify_cert=False)
        except:
            raise ValueError("    UNABLE TO CONNECT TO AGOL")
        
        self.agol_item = self.gis.content.get(self.item_id)

        # AGOL item error handling - DOES ITEM have attribute 'layers'?
        if hasattr(self.agol_item, 'layers'):
            print(f"    AGOL ITEM {self.item_id} HAS ATTRIBUTES 'layers")
        else:
            raise ValueError(f"     AGOL ITEM {self.item_id} DOES NOT HAVE ATTRIBUTE <layers>")
        
        # AGOL item error handling - DOES ITEM have one, and only one, layer?
        try:
            item_count = self.agol_item.layers
            if len(item_count) == 1:
                print("    SINGLE LAYER DETECTED")
            elif len(item_count) < 1:
                raise ValueError("ERROR - NO LAYERS DETECTED")
            elif len(item_count) > 1:
                raise ValueError("ERROR - MORE THAN ONE LAYER DETECTED")
        except:
            raise ValueError(f"ERROR - Unknown Problem")

        # Create Feature Layer Property 
        self.feature_layer = self.agol_item.layers[0]

        # Check for Mandatory Fields for All Forms (Taken from Input)
        Standard_Fields = ['objectid','CreationDate', 'what_is_your_email', 'submission_status']
        self.mandatory_Fields = list(set(Standard_Fields) | set(field_list)) #Combine Standard Mandatory Fields and the Input Ones into non duplicate list
        self.fc_fields = self.feature_layer.properties.fields
        self.fc_fields_list = [field['name'] for field in self.fc_fields]
        missing_fields = [field for field in self.mandatory_Fields if field not in self.fc_fields_list]
        if len(missing_fields) == 0:
            print("    ALL REQUIRED FIELDS ARE PRESENT")
        else:
            raise ValueError(f"    MISSING THE FOLLOWING REQUIRED FIELDS: {missing_fields}")

        # Check for new Submissions 
        self.new_oids = []
        features = self.feature_layer.query(where="submission_status <> 'Complete' OR submission_status IS NULL OR submission_status =''", out_fields=self.mandatory_Fields)
        for feature in features:
            self.new_oids.append(feature.attributes["objectid"])
        
        if len(self.new_oids) > 0:
            print(f"    {len(self.new_oids)} NEW RECORDS DETECTED")
            print(f"    AWAITING FURTHER INSTRUCTIONS")
        else:
            print(f"    NO NEW SUBMISSIONS - END OF SCRIPT")
            exit
            
    def delete_all_features(self):
        """
        USED PRIMARILY FOR TESTING. REQUIRES MANUAL VERIFICATION. WILL NOT WORK WHEN TRIGGERED BY 
        JENKINS/ REMOTELY.

        DELETES ALL DATA IN AGOL FC.
        """    
        delete_confirmation = input("TYPE 'YES' to confirm you want to delete all features. This cannot be reversed")

        if delete_confirmation == "YES":
            query_result = self.feature_layer.query(where='1=1', return_ids_only=True)
            delete_result = self.feature_layer.edit_features(deletes=str(query_result['objectIds']))            

class AGOL_SURVEY_FEATURE:
    """
    THIS CLASS IS MEANT TO HANDLE INDIVUDAL SUBMISSIONS TO A SURVEY (EG, 
    A SINGLE FEATURE). IT IS ALSO FOR DEFINING THE WORKSPACE FOR ANALYSIS
    (EG, DECARING ARCGIS ENV PARAMETERS) AND PREPROCESSING THE SPATIAL
    DATA. 

    ASSUMES THAT THE PRIMARY KEY FIELD BEING USED IS THE 'objectid'
    """

    def __init__(self, AGOL_SURVEY_CONNECTION, primary_key, primary_key_field='objectid'):
        print("")
        print(f"INITALIZING FEATURE AND ANALYSIS ENVIRONMENT FOR FEATURE {primary_key}")
        self.AGOL_SURVEY_CONNECTION = AGOL_SURVEY_CONNECTION
        self.primary_key_field = primary_key_field
        self.primary_key = primary_key
        self.feature = self.AGOL_SURVEY_CONNECTION.feature_layer.query(where=f"{primary_key_field} = '{primary_key}'", out_fields='*')

        # USED FOR CREATING THE BACKUP FOLDER FOR ALL RECORDS SUBMITTED TO S123. DIRECTORY CREATED BASED ON ITEM ID AND OBJECT ID
        self.archive_directory = r"\\spatialfiles.bcgov\Archive\srm\sry\Local\ArcGISOnline\S123_DATA__BACKUPS"
        self.archive_folder = os.path.join(self.archive_directory, f"ARCHIVE_{self.AGOL_SURVEY_CONNECTION.item_id}")
        
        if not os.path.exists(self.archive_folder):
            print("    ARCHIVE FOLDER NOT FOUND")
            os.makedirs(self.archive_folder)
            print("    ARCHIVE FOLDER CREATED")
        else:
            print("    ARCHIVE FOLDER FOUND")

        # CREATE ARCHIVE FOLDER FOR THE SPECIFIC FEATURE - Overwrite if it Exists Already
        self.feature_backup_folder = os.path.join(self.archive_folder, f"FEATURE_{self.primary_key}")
        if not os.path.exists(self.feature_backup_folder):
            print("    ARCHIVE FEATURE FOLDER NOT FOUND")
            os.makedirs(self.feature_backup_folder)
            print("    ARCHIVE FEATURE FOLDER CREATED")
        else:
            shutil.rmtree(self.feature_backup_folder)
            os.makedirs(self.feature_backup_folder)
            print("    ARCHIVE FEATURE FOLDER OVERWRITTEN")

        

        # SOME ERROR HANDLING (EG - SHOULD ONLY BE ABLE ACCEPET SINGLE PART GEOMETRY?)

    def change_feature_status(self, update_field, new_status):
        """
        USED FOR TRACKING PROGRESS ON ANALYSIS REQUESTS:
        1. "Submitted" (IE, successfully added via S123 but no other action)
        2. "In Progrees" (Currently being "touched" by this script)
        3. "Complete" (Process Started and Email with attached report successfully Sent)
        4. "Failed" (Process Started / Made set to In Progress, but not successfully completed)
        """
        feature_to_update = self.feature.features[0]
        previous_status = feature_to_update.attributes[update_field]
        feature_to_update.attributes[update_field] = new_status
        self.AGOL_SURVEY_CONNECTION.feature_layer.edit_features(updates=[feature_to_update])
        print(f"    Status of Object {object_id} has been updated from '{previous_status}' to '{new_status}'")

    def prepare_spatial_data(self):
        """
        FOR EASIER HANDLING AND FUTURE INTEROPERABILITY, THIS FUNCTION 
        EXTRACTS THE JSON FROM AGOL AND SAVES IT AS THE FOLLOWING:
        1. GeoJSON
        2. KML
        3. SHAPEFILE
        """
        print("    CREATING ARCHIVE OF SPATIAL DATA")
        sdf = self.feature.sdf
        # HANDLE DATA TYPE CONVERSION (Required for GeoJSON)
        for column in sdf.columns:
            if pd.api.types.is_float_dtype(sdf[column]):
                sdf[column] = sdf[column].astype(float)


        gdf = gpd.GeoDataFrame(sdf, geometry='SHAPE')

        # SAVE AS GeoJSON
        gdf.to_file(f"{self.feature_backup_folder}/{self.primary_key_field}_{self.primary_key}.geojson",driver='GeoJSON')
        
        # SAVE AS KML (Required import of Fiona KML Driver)
        fiona.supported_drivers['KML'] = "rw"
        gdf.to_file(f"{self.feature_backup_folder}/{self.primary_key_field}_{self.primary_key}.kml",driver='KML')

        # SAVE AS Shapefile (Requires Handling of Datetime Fields)
        for col in sdf.columns:
            if pd.api.types.is_datetime64_any_dtype(sdf[col]):
                sdf[col] = sdf[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        gdf = gpd.GeoDataFrame(sdf, geometry="SHAPE")

        if gdf.crs is None:
            gdf.set_crs(epsg=4236, inplace=True)
        # gdf = gdf.to_crs(epsg=3005)

        gdf.to_file(f"{self.feature_backup_folder}/{self.primary_key_field}_{self.primary_key}",driver='ESRI Shapefile')
        shutil.make_archive(f"{self.feature_backup_folder}/{self.primary_key_field}_{self.primary_key}", 'zip', f"{self.feature_backup_folder}/{self.primary_key_field}_{self.primary_key}")

class MAMU_AGOL_TOOLS:

    def __init__(self, input_shape, email, oid, population_shapes, provincial_dem):
        """
        This constructor is a specialized method used to initialize newly 
        created objects. It is automatically called whena new instance of
        this class is created. The main purpose is to assign values to 
        the object properties and perform any necessary initialization 
        tasks.  

        The configuration of the arcpy environment is included in this
        constructor. 
        """
        self.input_shape = input_shape
        self.email = email
        self.oid = oid
        self.population_shapes = population_shapes
        self.provincial_dem = provincial_dem
        
        # arcpy env configuration 
        arcpy.env.workspace = r"\\spatialfiles.bcgov\work\srm\sry\Workarea\emillan\MAMU\SCRIPT\MAMU_Screening\MAMU_Screening_Workspace\MAMU_Screening_Workspace.gdb"
        arcpy.env.overwriteOutput = True
        arcpy.env.parallelProcessingFactor = "100%"

        # check out required 
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
            print("Spatial Analyst License Acquired")
        else:
            print("Error - License Not Available")

        # bcgw connection 
        oracle_username, oracle_password, agol_username, agol_password = get_credentials("oracle", "agol")
        connection_name = "bcgw"
        bcgw_path = r"\\spatialfiles.bcgov\work\srm\sry\Workarea\emillan\MAMU\SCRIPT\MAMU_Screening\MAMU_Screening_Workspace"
        self.bcgw_name = f'{connection_name}.sde'
        try:
            create_bcgw_connection(oracle_password=oracle_password, oracle_username=oracle_username, bcgw_connection=f"{bcgw_path}\{self.bcgw_name}")
            print("BCGW CONNECTION SUCCESSFUL")
        except Exception as e:
            print("FAILED TO CREATE DATABASE CONNECTION")

        # datapaths 
        self.vri = f'{bcgw_path}/{self.bcgw_name}/WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY'

    def prepare_input_shape_dem(self):
        """
        """
        outExtractByMask = arcpy.sa.ExtractByMask(self.provincial_dem, self.input_shape, "INSIDE")
        temp_file = r"\\spatialfiles.bcgov\work\srm\sry\Workarea\emillan\MAMU\SCRIPT\MAMU_Screening\MAMU_Screening_Workspace\raster_wha_class_test.tif"
        outExtractByMask.save(temp_file)

    def create_vri_rasters(self, var_name, output_name, type, use_existing=True):
        """
        The "use existing" parameter is set to default true. If a raster with the specified name already exists, then this script will not create
        new ones and will continue. 
        """
        if os.path.exists(output_name) and use_existing == True:
            print(f"File {output_name} Exists")
        else:
            print("File Does Not Exist - Creating Rasters")


            if type == "POPULATION":
                # the vri is already clipped and saved as a separate feature class in order to enhance comp time.
                arcpy.PolygonToRaster_conversion("WHSE_FOREST_VEG_PairwiseClip", value_field=var_name, out_rasterdataset=output_name, cell_assignment="CELL_CENTER", cellsize=10)
            
            elif type == "SAMPLE":
                # the 'sample' represent the input shape and the entire vri will be clipped to this. at some point error handling to prevent large files should be put in place
                arcpy.analysis.Clip(
                in_features=self.vri,
                clip_features=self.input_shape,
                out_feature_class=r"temp_clip",
                cluster_tolerance=None)

                # arcpy.conversion.FeatureToRaster("temp_clip", field, output_name, 10)
                arcpy.PolygonToRaster_conversion("temp_clip", value_field=var_name, out_rasterdataset=output_name, cell_assignment="CELL_CENTER", cellsize=10)

    def create_distribution(self, image, type):
        """
        """
        print("Creating Distributions")
        # There are limits on pixel sizes using PILLOW to prevent dox attacks. This param raises the limit
        PIL.Image.MAX_IMAGE_PIXELS = 10000000000 

        if type == "POPULATION":
            # Create Normal Distribution of the Population
            print("Creating Population Distribution")
            with PIL.Image.open(image) as img:
                data=np.array(img)
                values = data.flatten()
                population_values_nonzero = values[values != 65535]
                population_values_nonzero = population_values_nonzero[population_values_nonzero >= 0]

            # KDE plot for the population
            ax = sns.kdeplot(population_values_nonzero, bw_adjust=0.75, label='Population Distribution', color='#E3A92C', linewidth=2)
            population_mean = np.mean(population_values_nonzero)
            plt.axvline(population_mean, color='r', linestyle='dashed', linewidth=2, label='Population Mean')
        
        elif type == "SAMPLE":
        # Create Normal Distribution of the Sample (The input Shape)
            print("Creating Sample Histogram")
            with PIL.Image.open(image) as img:
                data=np.array(img)
                values = data.flatten()
                sample_values_nonzero = values[values != 65535]
                sample_values_nonzero = sample_values_nonzero[sample_values_nonzero >= 0]
            
        print("drawing shape")
        plt.figure(figsize=(10, 6))
        plt.xlabel('Value')
        plt.ylabel('Density')
        plt.title('Distribution of Sample vs. Population')
        plt.legend(loc='upper right')
        plt.hist(sample_values_nonzero, bins=50, label='Sample', density=True, color="#003366")  # `density=True` normalizes the histograms
        plt.show()


# %%**********************************************************************
# TEST SPACE                                                            **
# ************************************************************************
GIS_CONNECTION = AGOL_SURVEY_CONNECTION("c65e0223d8e44d33aaf9aad799c6876a", field_list=[])
for object_id in GIS_CONNECTION.new_oids:
    FEATURE = AGOL_SURVEY_FEATURE(GIS_CONNECTION, primary_key=object_id)
    FEATURE.change_feature_status(update_field='submission_status', new_status="IN PROGRESS") 
    FEATURE.prepare_spatial_data()



















