from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import DecisionTreeRegressor
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql.functions import col, sum as spark_sum
import numpy as np
import os

# Initialisation de la session Spark
spark = SparkSession.builder \
    .appName("Analyse Avancée Location Vélos") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("Session Spark créée avec succès!")

# Chargement des données depuis HDFS
hdfs_file_path = "hdfs://namenode:8020/projetbigdata/Bike.csv"
print(f"Chargement des données depuis: {hdfs_file_path}")

try:
    # Lecture du fichier CSV
    df = spark.read.csv(hdfs_file_path, header=True, inferSchema=True)
    
    # Affichage du schéma pour vérifier le chargement
    print("Structure du DataFrame:")
    df.printSchema()
    
    # Affichage d'un échantillon de données
    print("Échantillon de données:")
    df.show(5)
    
    # Comptage des lignes
    row_count = df.count()
    print(f"Nombre total d'enregistrements: {row_count}")
    
    # Vérification des valeurs manquantes
    print("\nVérification des valeurs manquantes:")
    for column in df.columns:
        missing_count = df.filter(col(column).isNull()).count()
        if missing_count > 0:
            print(f"Colonne '{column}': {missing_count} valeurs manquantes")
    
    # Prétraitement: Suppression de la colonne datetime si elle existe
    if 'datetime' in df.columns:
        df = df.drop('datetime')
        print("Colonne 'datetime' supprimée")
    
    # Vérification de l'existence des colonnes requises
    required_columns = ['season', 'temp', 'humidity', 'windspeed', 'registered', 'count']
    for col_name in required_columns:
        if col_name not in df.columns:
            raise ValueError(f"Colonne requise '{col_name}' non trouvée dans le CSV")
    
    # Analyse descriptive simple
    print("\nAnalyse descriptive des données numériques:")
    df.select(['temp', 'humidity', 'windspeed', 'registered', 'count']).describe().show()
    
    df = df.withColumn("season", df["season"].cast("double"))
    df = df.withColumn("temp", df["temp"].cast("double"))
    df = df.withColumn("humidity", df["humidity"].cast("double"))
    df = df.withColumn("windspeed", df["windspeed"].cast("double"))
    df = df.withColumn("registered", df["registered"].cast("double"))
    df = df.withColumn("count", df["count"].cast("double"))
    
    # Calcul de statistiques par saison
    print("\nMoyenne des locations par saison:")
    df.groupBy("season").agg({"count": "avg"}).orderBy("season").show()
    
    # Division des données: 75% entraînement, 25% test (différent du 80/20 original)
    train_df, test_df = df.randomSplit([0.75, 0.25], seed=123)
    print(f"Taille de l'ensemble d'entraînement: {train_df.count()}")
    print(f"Taille de l'ensemble de test: {test_df.count()}")
    
    # Ingénierie des caractéristiques: ajout de plus de colonnes
    feature_cols = ['season', 'temp', 'humidity', 'windspeed', 'registered']
    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
    
    # Transformation des datasets pour inclure les vecteurs de caractéristiques
    train_data = assembler.transform(train_df)
    test_data = assembler.transform(test_df)
    
    # Initialisation du modèle Decision Tree (au lieu de Linear Regression)
    dt = DecisionTreeRegressor(featuresCol="features", labelCol="count", maxDepth=5)
    
    # Entraînement du modèle
    print("\nEntraînement du modèle d'arbre de décision...")
    model = dt.fit(train_data)
    
    # Afficher quelques informations sur le modèle
    print(f"Profondeur de l'arbre: {model.getMaxDepth()}")
    
    # Déterminer l'importance des caractéristiques
    feature_importances = model.featureImportances
    for i, importance in enumerate(feature_importances):
        print(f"Importance de {feature_cols[i]}: {importance:.4f}")
    
    # Prédictions sur les données de test
    predictions = model.transform(test_data)
    print("\nExemples de prédictions:")
    predictions.select("registered", "count", "prediction").show(5)
    
    # Évaluation du modèle avec différentes métriques
    print("\nÉvaluation du modèle:")
    
    # RMSE - racine de l'erreur quadratique moyenne
    evaluator = RegressionEvaluator(labelCol="count", predictionCol="prediction", metricName="rmse")
    rmse = evaluator.evaluate(predictions)
    print(f"Racine de l'erreur quadratique moyenne (RMSE): {rmse:.2f}")
    
    # R² - coefficient de détermination
    r2_evaluator = RegressionEvaluator(labelCol="count", predictionCol="prediction", metricName="r2")
    r2 = r2_evaluator.evaluate(predictions)
    print(f"Coefficient de détermination (R²): {r2:.2f}")
    
    # MSE - erreur quadratique moyenne
    mse_evaluator = RegressionEvaluator(labelCol="count", predictionCol="prediction", metricName="mse")
    mse = mse_evaluator.evaluate(predictions)
    print(f"Erreur quadratique moyenne (MSE): {mse:.2f}")
    
    # MAE - erreur absolue moyenne (métrique supplémentaire)
    mae_evaluator = RegressionEvaluator(labelCol="count", predictionCol="prediction", metricName="mae")
    mae = mae_evaluator.evaluate(predictions)
    print(f"Erreur absolue moyenne (MAE): {mae:.2f}")
    
    # Comparaison avec modèle naïf (prédiction = moyenne)
    avg_count = train_df.select(spark_sum("count") / spark_sum(lit(1))).collect()[0][0]
    
    print(f"\nComparaison avec un modèle naïf (prédiction = {avg_count:.2f}):")
    from pyspark.sql.functions import lit
    naive_predictions = test_df.withColumn("naive_prediction", lit(avg_count))
    naive_evaluator = RegressionEvaluator(labelCol="count", predictionCol="naive_prediction", metricName="rmse")
    naive_rmse = naive_evaluator.evaluate(naive_predictions)
    
    print(f"RMSE du modèle naïf: {naive_rmse:.2f}")
    improvement = ((naive_rmse - rmse) / naive_rmse) * 100
    print(f"Amélioration relative: {improvement:.2f}%")
    
    print("\nAnalyse complétée avec succès!")
    
except Exception as e:
    print(f"Erreur pendant l'analyse: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    # Arrêt de la session Spark
    spark.stop()
    print("Session Spark arrêtée.")