# Modèle SaaS Server

## Vue d'ensemble

Le modèle `saas.server` permet de gérer et monitorer les serveurs Odoo qui hébergent les instances SaaS. Chaque serveur peut héberger plusieurs instances clients.

## Fonctionnalités principales

### 1. Configuration du serveur
- **Informations de base** : Nom, code unique, description
- **URL et accès** : URL du serveur, adresse IP, port, credentials SSH
- **Configuration PostgreSQL** : Host, port, user, password, master password
- **Ressources** : CPU cores, mémoire (GB), espace disque (GB)

### 2. Gestion de la capacité
- **Max instances** : Nombre maximum d'instances que le serveur peut héberger
- **Instance count** : Nombre actuel d'instances hébergées (calculé automatiquement)
- **Available capacity** : Pourcentage de capacité disponible (calculé automatiquement)

### 3. Monitoring
- **État du serveur** : Draft, Active, Maintenance, Offline, Disabled
- **Statut de santé** : Healthy, Warning, Critical, Unknown
- **Vérification en ligne** : Vérification automatique de l'état du serveur via RPC
- **Dernière vérification** : Timestamp de la dernière vérification de santé

### 4. Actions disponibles

#### action_check_health()
Vérifie l'état de santé du serveur en tentant une connexion RPC.
- Met à jour `health_status` et `last_check_date`
- Change l'état en `active` si le serveur est en ligne, `offline` sinon

#### action_activate()
Active le serveur après vérification de la connexion.
- Teste d'abord la connexion au serveur
- Change l'état à `active` et `health_status` à `healthy`

#### action_deactivate()
Désactive le serveur (seulement si aucune instance n'est hébergée).

#### action_maintenance()
Met le serveur en mode maintenance.

#### action_test_connection()
Teste la connexion au serveur (affiche une notification du résultat).

#### action_view_instances()
Affiche toutes les instances hébergées sur ce serveur.

### 5. Méthodes utilitaires

#### _test_connection()
Teste la connexion RPC au serveur via le endpoint `/jsonrpc`.
Utilise le service `common.version` pour vérifier la disponibilité.

Retourne : `bool` (True si la connexion est réussie)

#### get_available_server(min_capacity_percent=20)
Classe method pour obtenir un serveur disponible avec suffisamment de capacité.

```python
server = self.env['saas.server'].get_available_server(min_capacity_percent=20)
```

Lève `UserError` si aucun serveur disponible n'est trouvé.

## Flux de travail typique

### 1. Créer un nouveau serveur
1. Accédez à **SaaS Manager > Configuration > Servers**
2. Cliquez sur **Create**
3. Remplissez les informations de base (nom, code, URL du serveur)
4. Configurez la connexion PostgreSQL
5. Définissez les ressources du serveur (CPU, mémoire, disque)
6. Sauvegardez

### 2. Activer le serveur
1. Cliquez sur le bouton **Test Connection** pour vérifier la connexion
2. Si le test réussit, cliquez sur **Activate**
3. Le serveur est maintenant prêt à héberger des instances

### 3. Monitorer le serveur
1. Utilisez le bouton **Check Health** pour vérifier l'état
2. Consultez les métriques de capacité disponible
3. Consultez l'historique des vérifications de santé

### 4. Créer une instance sur ce serveur
```python
server = self.env['saas.server'].get_available_server()
instance = self.env['saas.instance'].create({
    'name': 'Client Instance',
    'database_name': 'client_db',
    'subdomain': 'client',
    'template_id': template.id,
    'plan_id': plan.id,
    'server_id': server.id,  # Lier au serveur
    'partner_id': partner.id,
})
```

## Sécurité

- **Groupes d'accès** :
  - `group_saas_user` : Lecture seule
  - `group_saas_manager` : Lecture/Écriture (pas création/suppression)
  - `group_saas_admin` : Accès complet

- **Contraintes** :
  - Code unique (lowercase obligatoire)
  - URL du serveur unique
  - URL doit commencer par `http://` ou `https://`
  - `max_instances` doit être > 0
  - Impossible de supprimer un serveur avec des instances hébergées

## Intégration avec SaaS Instance

Le modèle `saas.instance` a été mis à jour avec un champ `server_id` pour lier chaque instance à un serveur.

```python
class SaaSInstance(models.Model):
    _name = 'saas.instance'
    
    server_id = fields.Many2one(
        'saas.server',
        string='Server',
        required=True,
        tracking=True,
        ondelete='restrict',
        domain="[('state', '=', 'active'), ('available_capacity', '>', 0)]",
        default=lambda self: self._get_default_server(),
        help="Server hosting this instance"
    )
```

### Auto-sélection du serveur

Lors de la création d'une instance, le serveur avec le plus de capacité disponible est automatiquement sélectionné :

```python
def _get_default_server(self):
    """
    Obtenir le serveur par défaut avec le plus de capacité disponible.
    """
    Server = self.env['saas.server']
    try:
        return Server.get_available_server(min_capacity_percent=10)
    except UserError:
        # If no server with 10% capacity, try to get any active server
        return Server.search([('state', '=', 'active')], limit=1)
```

### Validation lors du provisioning

Avant de provisionner une instance, le système valide :
1. **État du serveur** : Le serveur doit être `active`
2. **Capacité disponible** : Au moins 10% de capacité disponible
3. **Même serveur que le template** : Le template et l'instance doivent être sur le même serveur

## Intégration avec SaaS Template

Le modèle `saas.template` a été mis à jour avec un champ `server_id` pour lier chaque template à un serveur.

```python
class SaaSTemplate(models.Model):
    _name = 'saas.template'
    
    server_id = fields.Many2one(
        'saas.server',
        string='Server',
        required=True,
        domain="[('state', '=', 'active')]",
        help="Server where this template database is hosted"
    )
```

### Création de template

Lors de la création d'un template, le système utilise la configuration du serveur :
- **URL RPC** : `self.server_id.server_url` pour les appels RPC
- **Master password** : `self.server_id.master_password` pour la création de la base de données
- **Validation** : Le serveur doit être `active` avant de créer un template

### Clonage de template

Lors du clonage d'un template PostgreSQL, le système utilise les paramètres de connexion du serveur :
- **DB Host** : `self.server_id.db_host`
- **DB Port** : `self.server_id.db_port`
- **DB User** : `self.server_id.db_user`
- **DB Password** : `self.server_id.db_password`

## Gestion de la capacité des serveurs

Le système surveille automatiquement la capacité des serveurs :

### Métriques de capacité
- **max_instances** : Nombre maximum d'instances configuré
- **instance_count** : Nombre actuel d'instances (calculé dynamiquement)
- **available_capacity** : Pourcentage de capacité disponible

### Calcul de la capacité
```python
available_capacity = ((max_instances - instance_count) / max_instances) * 100
```

### Seuils recommandés
- **Minimum 10%** : Pour le provisioning d'instances
- **Minimum 20%** : Pour la recherche de serveur via `get_available_server()`
- **Alerte 90%** : Serveur proche de la capacité maximale
- **Bloqué 100%** : Serveur à pleine capacité

## Monitoring automatique

### Cron de vérification de santé

Un cron s'exécute toutes les heures pour vérifier la santé de tous les serveurs actifs :

```python
@api.model
def cron_check_all_servers_health(self):
    """
    CRON: Vérifier la santé de tous les serveurs actifs.
    """
    servers = self.search([('state', 'in', ['active', 'maintenance'])])
    
    for server in servers:
        try:
            server.action_check_health()
        except Exception as e:
            _logger.error(f"Health check failed for server {server.name}: {str(e)}")
```

### Configuration du cron
- **Nom** : `SaaS: Check Server Health`
- **Fréquence** : Toutes les heures
- **Actif** : Oui
- **Modèle** : `saas.server`
- **Code** : `model.cron_check_all_servers_health()`

### Résultats de la vérification
- **healthy** : Serveur en ligne et fonctionnel
- **critical** : Serveur hors ligne ou erreur
- **État du serveur** : Mis à jour automatiquement (`active` ou `offline`)
- **last_check_date** : Timestamp de la dernière vérification

## Architecture multi-serveurs

### Scénario typique : 100+ instances

#### Configuration initiale
1. **Serveur 1** : Production Principal (max 50 instances)
2. **Serveur 2** : Production Secondaire (max 50 instances)
3. **Serveur 3** : Développement/Test (max 20 instances)

#### Flux de provisioning automatique

1. **Client crée une instance**
   - Le système sélectionne automatiquement le serveur avec le plus de capacité
   - Vérifie que le serveur est `active`
   - Vérifie qu'il reste au moins 10% de capacité

2. **Clonage du template**
   - Vérifie que le template et l'instance sont sur le même serveur
   - Clone la base de données PostgreSQL en ~5 secondes
   - Utilise les credentials du serveur

3. **Monitoring continu**
   - Vérification de santé toutes les heures
   - Mise à jour des métriques de capacité
   - Alertes en cas de problème

### Avantages de l'architecture

- ✅ **Scalabilité** : Ajoutez des serveurs selon les besoins
- ✅ **Isolation** : Séparez production et développement
- ✅ **Performance** : Répartition de charge automatique
- ✅ **Fiabilité** : Monitoring automatique et alertes
- ✅ **Flexibilité** : Templates peuvent être migrés entre serveurs
- ✅ **Visibilité** : Métriques de capacité en temps réel

## API RPC

Le serveur utilise l'API RPC d'Odoo pour la communication :

### Test de connexion
```json
{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "service": "common",
        "method": "version"
    },
    "id": 1
}
```

## Logging

Tous les événements sont enregistrés dans les logs :
- Création de serveur
- Changement d'état
- Vérifications de santé
- Tentatives de connexion

Consultez les logs avec la clé : `odoo.addons.saas_manager.models.saas_server`

## À venir (Phase 2)

- [ ] Monitoring en temps réel via Prometheus
- [ ] Alertes automatiques en cas de problème
- [ ] Migration d'instances entre serveurs
- [ ] Load balancing automatique
- [ ] Backup automatique
- [ ] Replication haute disponibilité

