# Zoraxy Reverse Proxy — Intégration Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/juju35/ha-zoraxy/actions/workflows/validate.yml/badge.svg)](https://github.com/juju35/ha-zoraxy/actions/workflows/validate.yml)
[![GitHub Release](https://img.shields.io/github/release/juju35/ha-zoraxy.svg)](https://github.com/juju35/ha-zoraxy/releases)

Dashboard de monitoring complet pour [Zoraxy](https://github.com/tobychui/zoraxy) (v3.3.2+), le reverse proxy Go, intégré dans Home Assistant.

---

## Installation via HACS (recommandé)

### Prérequis
[HACS](https://hacs.xyz) doit être installé dans votre Home Assistant.

### Ajouter le dépôt

Cliquez sur le bouton ci-dessous pour ajouter ce dépôt directement dans HACS :

[![Ajouter à HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=juju35&repository=ha-zoraxy&category=integration)

Ou manuellement :

1. Ouvrir HACS dans Home Assistant
2. Aller dans **Intégrations** → ⋮ → **Dépôts personnalisés**
3. Ajouter `https://github.com/juju35/ha-zoraxy` — Catégorie : **Intégration**
4. Rechercher **Zoraxy** et cliquer **Télécharger**
5. Redémarrer Home Assistant

### Custom card Lovelace

La carte `zoraxy-card.js` est **incluse dans l'intégration** et déployée automatiquement dans `/config/www/` au démarrage. Pas besoin de l'installer séparément via HACS.

---

## Installation manuelle

### 1 — Copier les fichiers

```
/config/
├── custom_components/
│   └── zoraxy/          ← contenu du dossier custom_components/zoraxy/
└── www/
    └── zoraxy-card.js   ← fichier www/zoraxy-card.js
```

### 2 — Ressource Lovelace

La carte `zoraxy-card.js` est **automatiquement copiée et enregistrée** dans Lovelace au démarrage. Rien à faire manuellement.

> Si l'enregistrement automatique échoue, ajoutez manuellement dans Paramètres → Tableau de bord → ⋮ → Ressources :
> - URL : `/local/zoraxy-card.js` — Type : **Module JavaScript**

### 3 — Redémarrer Home Assistant

### 4 — Ajouter l'intégration

Paramètres → Appareils & Services → **+ Ajouter** → **Zoraxy**

- **Adresse** : `http://192.168.1.253:8000`
- **Nom d'utilisateur** / **Mot de passe** : identifiants Zoraxy
- **Intervalle de rafraîchissement** : 30 secondes

### 5 — Ajouter la carte Lovelace

```yaml
type: custom:zoraxy-card
zoraxy_url: http://192.168.1.253:8000
```

---

## Fonctionnalités

### Capteurs globaux
| Entité | Description |
|--------|-------------|
| `sensor.*_regles_proxy` | Nombre de règles proxy (détails en attributs) |
| `sensor.*_regles_actives` | Règles proxy actives |
| `sensor.*_certificats_tls` | Nombre de certificats TLS |
| `sensor.*_regles_d_acces` | Nombre de règles d'accès |
| `sensor.*_port_entrant` | Port d'écoute du proxy |

### Par certificat (créés dynamiquement)
| Entité | Description |
|--------|-------------|
| `sensor.*_cert_{domaine}` | Date d'expiration du certificat |
| `binary_sensor.*_cert_expirant_{domaine}` | `on` si expiration < 30 jours |
| `button.*_renouveler_{domaine}` | Déclenche le renouvellement ACME |

### Capteurs binaires
| Entité | Description |
|--------|-------------|
| `binary_sensor.*_proxy_actif` | Proxy en cours d'exécution |
| `binary_sensor.*_tls_active` | TLS activé |
| `binary_sensor.*_redirection_https` | Redirection HTTP→HTTPS |
| `binary_sensor.*_ecoute_port_80` | Écoute sur le port 80 |
| `binary_sensor.*_mode_developpement` | Mode développement (no-cache) |

### Switches
| Entité | Description |
|--------|-------------|
| `switch.*_redirection_https` | Active/désactive la redirection HTTPS |
| `switch.*_ecoute_port_80` | Active/désactive l'écoute port 80 |
| `switch.*_mode_developpement` | Active/désactive le mode développement |

### Services
| Service | Description |
|---------|-------------|
| `zoraxy.toggle_proxy_rule` | Active ou désactive une règle proxy |

#### `zoraxy.toggle_proxy_rule`

| Paramètre | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| `domain` | `string` | oui | Domaine de la règle (ex: `monapp.exemple.com`) |
| `enable` | `boolean` | oui | `true` pour activer, `false` pour désactiver |

Exemple d'utilisation dans une automatisation :

```yaml
action: zoraxy.toggle_proxy_rule
data:
  domain: monapp.exemple.com
  enable: false
```

---

## Custom Card

La carte Lovelace affiche :
- Statut du proxy + métriques
- Contrôles directs (HTTPS redirect, port 80, dev mode)
- Liste des certificats avec date d'expiration et bouton de renouvellement ACME
- Règles proxy avec **bouton d'activation/désactivation par règle**
- Redirections HTTP

### Activation/désactivation d'une règle depuis la carte

Chaque règle proxy dispose d'un bouton dans la colonne État :
- 🟢 point vert — règle active, cliquer pour désactiver
- 🔴 point rouge — règle désactivée, cliquer pour activer

Le changement est appliqué immédiatement via le service `zoraxy.toggle_proxy_rule` et la carte se met à jour automatiquement.

---

## Notes

- Nécessite Zoraxy **v3.3.2+**
- La session Zoraxy expire après ~1h — la reconnexion est automatique
- Multilingue : 🇫🇷 français et 🇬🇧 anglais
- Pour déboguer :
  ```yaml
  logger:
    logs:
      custom_components.zoraxy: debug
  ```

## Compatibilité

- Home Assistant **2023.1+**
- Zoraxy **v3.3.x**
