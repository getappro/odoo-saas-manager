# saas_backup_aws

Sauvegardes des instances SaaS vers AWS S3 (dump DB + filestore) via RPC `backup`, avec chiffrement SSE-S3, rétention des N dernières sauvegardes et backups automatiques.

## Installation

- Ajouter l’addon au `addons_path`.
- Installer l’externe `boto3` (requirements global Odoo).
- Installer le module depuis les Apps.

## Configuration

Menu Paramètres > AWS S3 Backups : renseigner clés, bucket, région, préfixe, rétention, activer l’auto backup si besoin. Bouton "Test S3" pour vérifier l’accès bucket.

## Utilisation

- Bouton "Backup S3" dans une instance pour déclencher un backup manuel.
- Smartbutton "Backups" pour consulter l’historique.
- Cron horaire déclenche les backups automatiques selon l’intervalle configuré.

