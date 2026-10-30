# bbox-epg

Programme TV des chaînes Bbox pour l'app « Télécommande pour Bbox ».

- Source : [XML TV Fr](https://xmltvfr.fr) (fichier France, téléchargé une fois par jour).
- `channels_map.json` : numéro de chaîne Bbox → identifiant XMLTV. Plusieurs numéros peuvent partager un identifiant.
- `build_epg.py` : filtre le guide sur ces chaînes, de 3 h avant à 4 jours après la génération, et écrit `site/epg.json`.
- `.github/workflows/epg.yml` : exécution quotidienne et publication sur GitHub Pages.

Format de `epg.json` :

```json
{
  "v": 1, "generated": 1793372400, "source": "XML TV Fr (xmltvfr.fr)",
  "map": { "1": "TF1.fr", "36": "TF1.fr" },
  "programmes": { "TF1.fr": [[1793372400, 1793377800, "Titre", "Sous-titre ou null", "Catégorie ou null"]] }
}
```

Heures en secondes depuis 1970 (UTC). Les apps ne téléchargent que ce fichier, jamais xmltvfr.fr directement.
