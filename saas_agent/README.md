# SaaS Agent

Module client à installer sur chaque instance SaaS pour être pilotée par `saas_manager` : quotas utilisateurs, SSO "login as" et synchronisation de secrets.

## Installation

1. Déposer le dossier `saas_agent` dans vos addons et mettre à jour le path.
2. Installer les dépendances Python (sur l’instance) :

```bash
pip install PyJWT
```

3. Installer le module depuis Apps : `SaaS Agent`.
4. Dans les paramètres techniques (`Paramètres > Technique > Paramètres système`), le secret `saas_agent.secret` est généré automatiquement à l’installation. Il sera poussé par le master via RPC.
5. (Optionnel) Définir l’utilisateur cible par défaut pour le SSO via `Paramètres > Général > SaaS Agent`.

## Utilisation

- Le master appelle les endpoints `/saas/set_user_limit`, `/saas/get_users_count` et `/saas/sso/request` en Bearer JWT signé avec `saas_agent.secret`.
- Le quota utilisateurs bloque toute création ou réactivation d'utilisateur interne dès que `saas_agent.user_limit` est atteint ou vaut 0. Les utilisateurs portail et système sont exclus du comptage.
- L’URL de connexion sans mot de passe est retournée par `/saas/sso/request` et redirige via `/saas/sso/login`.
- L’expiration/suspension est poussée par le master via `/saas/set_expiration` (date et flag). Quand la suspension est active ou la date dépassée, tout accès applicatif est bloqué jusqu’à désactivation depuis le master.
