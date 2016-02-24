"""
Contains functions for reading from and writing to the Tomnod DB.

Author: Kostas Stamatiou
Created: 02/23/2016
Contact: kostas.stamatiou@digitalglobe.com
"""

import geojson
from shapely.wkb import loads
import tomnodDB as DB


def train_geojson(schema, 
	              cat_id,
	              max_number, 
	              output_file, 
	              class_name, 
	              min_score=0.95, 
	              min_votes=0
	             ):
	"""Read features from Tomnod campaign and write to geojson.
	   The purpose of this function is to create training data for a machine.
	   Features are read from the DB in decreasing score order.
	   All features are from the same image and of the same class.

       Args:
           schema (str): Campaign schema.
           cat_id (str): Image catalog id.
           max_number (int): Maximum number of features to be read.
           output_file (str): Output file name (extension .geojson).
           class_name (str): Feature class (type in Tomnod jargon) name.
           min_score (float): Only features with score>=min_score will be read.
           min_votes (int): Only features with votes>=min_votes will be read.
	"""

	print 'Retrieve data for: ' 
	print 'Schema: ' + schema
	print 'Catalog id: ' + cat_id
	print 'Class name: ' + class_name

	query = """SELECT feature.id, feature.feature
		       FROM {}.feature, tag_type, overlay
		       WHERE feature.type_id = tag_type.id
		       AND feature.overlay_id = overlay.id
		       AND overlay.catalogid = '{}'
		       AND tag_type.name = '{}'
		       AND feature.score >= {}
		       AND feature.num_votes_total >= {}
		       ORDER BY feature.score DESC LIMIT {}""".format(schema, 
		           	                                          cat_id, 
		           	                                          class_name, 
		           	                                          min_score,
		           	                                          min_votes,
		           	                                          max_number)

	data = DB.db_fetch_array(query)

	# convert to GeoJSON
	geojson_features = [] 
	for entry in data:
		feature_id, coords_in_hex = entry
		polygon = loads(coords_in_hex, hex=True)
		coords = [list(polygon.exterior.coords)]   # the brackets are dictated
		                                           # by geojson format!!! 
		geojson_feature = geojson.Feature(geometry = geojson.Polygon(coords), 
			                              properties={"id": str(feature_id), 
			                                          "class_name": class_name, 
			                                          "image_name": cat_id})
		geojson_features.append(geojson_feature)
	
	feature_collection = geojson.FeatureCollection(geojson_features)	

	# store
	with open(output_file, 'wb') as f:
		geojson.dump(feature_collection, f)		 	   

	print 'Done!'


def target_geojson(schema, 
	               cat_id,
	               max_number, 
	               output_file, 
	               max_score=1.0,
	               max_votes=0 
	              ):

	"""Read features from Tomnod campaign and write to geojson.
       The purpose of this function is to create target data for a machine.
       Features are read from the DB in increasing score order, nulls first.
       (A feature with null score has not been viewed by a user yet.)
	   
       Args:
           schema (str): Campaign schema.
           cat_id (str): Image catalog id.
           max_number (int): Maximum number of features to be read.
           output_file (str): Output file name (extension .geojson).
           max_score (float): Only features with score<=max_score will be read.
		   max_votes (int): Only features with votes<=max_votes will be read.
	"""

	print 'Retrieve data for: ' 
	print 'Schema: ' + schema
	print 'Catalog id: ' + cat_id

	query = """SELECT feature.id, feature.feature, tag_type.name
			   FROM {}.feature, tag_type, overlay
		       WHERE feature.type_id = tag_type.id
	           AND {}.feature, overlay
	           AND feature.overlay_id = overlay.id
	           AND overlay.catalogid = '{}'
	           AND feature.score <= {}
	           AND feature.num_votes_total <= {}
	           ORDER BY feature.score ASC NULLS FIRST
	           LIMIT {}""".format(schema, 
	       	                      cat_id,  
	       	                      min_score,
	       	                      max_score, 
	       	                      max_number)          

	data = DB.db_fetch_array(query)

	# convert to GeoJSON
	geojson_features = [] 
	for entry in data:
		feature_id, coords_in_hex, class_name = entry
		polygon = loads(coords_in_hex, hex=True)
		coords = [list(polygon.exterior.coords)]   # the brackets are dictated
		                                           # by geojson format!!! 
		geojson_feature = geojson.Feature(geometry = geojson.Polygon(coords), 
			                              properties={"id": str(feature_id), 
			                                          "class_name": class_name, 
			                                          "image_name": cat_id})
		geojson_features.append(geojson_feature)
	
	feature_collection = geojson.FeatureCollection(geojson_features)	

	# store
	with open(output_file, 'wb') as f:
		geojson.dump(feature_collection, f)		 	   

	print 'Done!'	


def join_two_geojsons(file_1, file_2, output_file):
	"""Join two geojsons into one. The spatial reference system of the 
	   output file is the same as the one of file_1.

	   Args:
	       file_1 (str): Filename 1 (ext. geojson).
	       file_2 (str): Filename 2 (ext. geojson).
	       output_file (str): Output filename (ext. geojson).
	"""

	# get feature collections
	with open(file_1) as f:
	    feat_collection_1 = geojson.load(f)

	with open(file_2) as f:
	    feat_collection_2 = geojson.load(f)

	feat_final = feat_collection_1['features'] + feat_collection_2['features']  

	feat_collection_1['features'] = feat_final

	# write to output file
	with open(output_file, 'w') as f:
	    geojson.dump(feat_collection_1, f) 

    
def split_geojson(input_file, file_1, file_2, ratio):
	"""Split a geojson in two separate files.
	   
	   Args:
	       input_file (str): Input filename (ext. geojson).
	       file_1 (str): Output filename 1 (ext. geojson).
	       file_2 (str): Output filename 2 (ext. geojson).
	       ratio (float): Proportion of features in input_file that goes to 
	                      file_1. ratio is from 0 to 1.
	       output_file (str): Output filename (ext. geojson).
	"""

	# get feature collection
	with open(input_file) as f:
	    feat_collection = geojson.load(f)

	features = feat_collection['features']
	no_features = len(features)
	no_features_1 = int(round(ratio*no_features))
	feat_collection_1 = geojson.FeatureCollection(features[0:no_features_1])
	feat_collection_2 = geojson.FeatureCollection(features[no_features_1:])

	with open(file_1, 'w') as f:
	    geojson.dump(feat_collection_1, f) 

	with open(file_2, 'w') as f:
		geojson.dump(feat_collection_2, f) 	


