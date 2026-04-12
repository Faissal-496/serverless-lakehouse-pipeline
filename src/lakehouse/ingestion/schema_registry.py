# src/lakehouse/ingestion/schema_registry.py
from pyspark.sql.types import (
    StructType,
    StructField,
    IntegerType,
    StringType,
    DoubleType,
)

# -----------------------------
# Schéma Bronze pour Contrat2
# -----------------------------
# Les champs sont permissifs (nullable=True) car Bronze est la couche raw
CONTRAT2_SCHEMA = StructType(
    [
        # Identifiant unique sociétaire
        StructField("nusoc", IntegerType(), True),
        # Numéro de contrat associé au sociétaire
        StructField("nucon", IntegerType(), True),
        # Type de véhicule : 'A' Auto, 'M' Moto, 'C' Cyclo
        StructField("cateco", StringType(), True),
        # Garanties assurées (0 = non, 1 = oui)
        StructField("g01co", IntegerType(), True),  # Responsabilité Civile
        StructField("g02co", IntegerType(), True),  # Défense recours
        StructField("g03co", IntegerType(), True),  # Vol
        StructField("g04co", IntegerType(), True),  # Incendie
        StructField("g05co", IntegerType(), True),  # Catastrophes naturelles
        StructField("g06co", IntegerType(), True),  # Bris de glace
        StructField("g09co", IntegerType(), True),  # Dommages Tous Accidents
        StructField("g10co", IntegerType(), True),  # Outil de travail
        StructField("g13co", IntegerType(), True),  # Corporelle 1
        StructField("g15co", IntegerType(), True),  # Corporelle 3
        StructField("g16co", IntegerType(), True),  # Corporelle Scolaire
        StructField("g17co", IntegerType(), True),  # Catastrophes technologiques
        StructField("g18co", IntegerType(), True),  # Objets transportés
        StructField("g19co", IntegerType(), True),  # Assistance au véhicule
        StructField("g21co", IntegerType(), True),  # Assistance aux personnes
        StructField("g22co", IntegerType(), True),  # RC Hors Circulation
        StructField("g23co", IntegerType(), True),  # Accessoires Vol
        StructField("g25co", IntegerType(), True),  # Accessoires Dommages
        StructField("g26co", IntegerType(), True),  # Equipement
        StructField("g28co", IntegerType(), True),  # Moto transportée
        # Classification interne du contrat
        StructField("clasco", StringType(), True),
        # Tarif applicatif
        StructField("tar6co", StringType(), True),
        # Montant bonus/malus
        StructField("bomaco", DoubleType(), True),
        # Fréquence de paiement : Annuel, Mensuel, Trimestriel, etc.
        StructField("fracco", StringType(), True),
        # Famille du véhicule
        StructField("famgta", StringType(), True),
        # Marque du véhicule
        StructField("markli", StringType(), True),
        # Code de l’APC (assurance)
        StructField("apcoco", StringType(), True),
        # Année de circulation du véhicule
        StructField("acircu", IntegerType(), True),
        # Mois de circulation du véhicule
        StructField("mcircu", IntegerType(), True),
        # Année de reconstruction du véhicule
        StructField("acreco", IntegerType(), True),
        # Mois de reconstruction du véhicule
        StructField("mcreco", IntegerType(), True),
        # Jour de reconstruction du véhicule
        StructField("jcreco", IntegerType(), True),
        # Prime du contrat
        StructField("prmaco", DoubleType(), True),
        # Etat du contrat : 0=Annulé, 1=En cours, 2=Suspendu, etc.
        StructField("etatco", StringType(), True),
        # Age du sociétaire à la souscription
        StructField("asaico", IntegerType(), True),
        # Mois de naissance du sociétaire
        StructField("msaico", IntegerType(), True),
        # Jour de naissance du sociétaire
        StructField("jsaico", IntegerType(), True),
        # Type de véhicule (ex: Supersport, Enduro, Trail)
        StructField("utimot", StringType(), True),
        # Puissance fiscale du véhicule
        StructField("pfco", IntegerType(), True),
        # Usage principal : 0=domicile/travail, 1=promenade, 3=professionnel
        StructField("usagco1", IntegerType(), True),
    ]
)

# ====================================================================
# CONTRAT1_SCHEMA: Same structure as CONTRAT2_SCHEMA for union
# ====================================================================
# CONTRAT1 and CONTRAT2 use identical schema structure for union compatibility.
# If different in production, create a separate schema and use schema mapping.
CONTRAT1_SCHEMA = CONTRAT2_SCHEMA

# =====================================================
# Schéma Bronze pour Client
# =====================================================
CLIENT_SCHEMA = StructType(
    [
        StructField("nusoc", IntegerType(), True),  # Identifiant unique sociétaire
        StructField("cdepso", StringType(), True),  # Code département
        StructField("cvilso", StringType(), True),  # Ville
        StructField("sexsoc", StringType(), True),  # Sexe : 1=Homme, 2=Femme, 3=Personne morale
        StructField("bgesso", StringType(), True),  # Base géographique (ex: 9=Bordeaux)
        StructField("aadhso", IntegerType(), True),  # Année de naissance
        StructField("anaiso", IntegerType(), True),  # Année d’ancienneté
        StructField("mnaiso", IntegerType(), True),  # Mois d’ancienneté
        StructField("jnaiso", IntegerType(), True),  # Jour d’ancienneté
        StructField("cspsoc", StringType(), True),  # Catégorie socio-professionnelle
        StructField("asaiso", StringType(), True),  # Situation familiale (ex: N=Ne vit pas en couple)
        StructField("msaico", IntegerType(), True),  # Mois naissance
        StructField("jsaiso", IntegerType(), True),  # Jour naissance
        StructField("sitmat", StringType(), True),  # Statut marital
        StructField("nbenf", IntegerType(), True),  # Nombre d’enfants
        StructField("accmai", StringType(), True),  # Accidents sur 12 mois
        StructField("accsms", StringType(), True),  # Accidents signalés par SMS
        StructField("sitpav1", StringType(), True),  # Situation pavillonnaire
    ]
)
