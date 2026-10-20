# AULA ARENA

Mini Web-FPS 3D in prima persona, stile cartoon/toon, ottimizzato per smartphone.
7 compagni di classe, una scuola da esplorare, un evento a sorpresa: **l'Interrogazione**.

React 18 · React Three Fiber · three.js · Tailwind · Vite.

## Avvio

```bash
cd games/aula-arena
npm install
npm run dev        # http://localhost:5173 (anche da telefono in LAN: vite --host)
npm run build      # produce dist/
npm run simtest    # test headless della simulazione (bot vs bot, regole evento, collisioni)
npm run balance    # kill/morti medi per loadout su più partite
```

Parametri URL di debug: `?event=8` (primo evento dopo 8 s), `?touch=1` (forza UI touch su desktop), `?debug=1` (espone `window.__aula`).

## Deploy su Vercel (da GitHub)

1. Vercel → *Add New Project* → importa il repo.
2. **Root Directory: `games/aula-arena`** (il repo è un monorepo).
3. Framework Preset: **Vite** (già in `vercel.json`). Build `npm run build`, output `dist`. Nessuna variabile d'ambiente.

## Come aggiungere le foto dei compagni

Copia i file in `public/avatars/` con questi nomi: `leonardo.jpg`, `stefano.jpg`, `seba.jpg`,
`riccardo.jpg`, `lorenzo.jpg`, `federico.jpg`, `ferdinando.jpg` (quadrati, volto centrato, ~512 px).
La stessa foto compare **nella scheda della lobby** e **sulla faccia del personaggio 3D** (ritagliata a cerchio
con contorno cartoon). Finché il file manca c'è un placeholder con le iniziali. Dettagli in `public/avatars/README.md`.
Per cambiare estensione o percorso: campo `photo` in `src/game/characters.js`.

## Controlli

| | Touch | PC |
|---|---|---|
| Muoversi | joystick fisso in basso a sinistra | WASD |
| Guardare | trascina sulla parte destra (anche tenendo premuto il tasto fuoco) | mouse (click = cattura il puntatore) |
| Sparare | 🎯 | click / Spazio |
| Superpotere | pulsante con anello di carica | E / Shift |
| Secondaria (cambio arma o gadget) | pulsante a sinistra del fuoco | Q / F |
| Ricarica | 🔄 | R |

Per il tocco c'è una piccola **assistenza alla mira** (cono di ~6° verso nemici in linea di vista).

## Regole

- **Tutti contro tutti** con 6 bot: vince chi arriva per primo a 15 uccisioni o ha più uccisioni allo scadere dei 5 minuti. Respawn dopo 3 s con 2 s di protezione.
- **Loadout** (scelto in lobby, ogni compagno ha il suo di serie): *Assalto* (fucile automatico + pistola), *Brawler* (fucile a pompa + scatto), *Tattico* (bazooka ad area + granata stordente). Bilanciati con `npm run balance` (±20% di K/D fra i tre).
- **Superpoteri** (5 s, carica con danni inflitti, uccisioni e tempo): Super-Velocità, Scudo Digitale, Proiettili Rimbalzanti, Raffica Infinita, Super Voto 10 (danno ×2), Modalità Fantasma, Pausa Merenda (rigenera vita).
- **Interrogazione a Sorpresa**: ogni 60-90 s compare l'allarme, la ruota gira 3 s ed estrae l'**Interrogato**. Per 7 s solo lui può sparare; tutti gli altri sono **Impreparati** (braccia abbassate, niente fuoco/granate/bazooka) ma possono correre e scattare.

## Struttura

```
src/
  App.jsx                 stato globale: lobby → partita → fine, pausa, fullscreen, wake-lock
  components/
    LobbyUI.jsx           lobby stile "operator": 7 schede con slot foto + scelta loadout
    Controls.jsx          joystick, area visuale, pulsanti (pointer events, zero setState nel gesto) + tastiera/mouse
    HUD.jsx / GameUI.jsx  HUD (vita, munizioni, kill feed, classifica, evento) + menu pausa
    EventWheel.jsx        ruota della fortuna
  scene/
    Scene3D.jsx           Canvas, loop di gioco, camera, risoluzione dinamica, pulizia memoria
    World.jsx             mappa fusa in 1 draw call + contorni cartoon
    Fighters.jsx          personaggi 3D (faccia = foto), animazioni, etichette
    ViewModel.jsx         braccia + arma in prima persona (render separato: non entra mai nei muri)
    Effects.jsx           tracer, esplosioni, proiettili (pool fissi, zero allocazioni per frame)
  game/                   logica pura, senza browser: testabile in Node
    sim.js  bots.js  nav.js  collision.js  map.js  weapons.js  characters.js  constants.js
```

## Note tecniche

- **Viewport fisso**: `position: fixed`, `overflow: hidden`, `touch-action: none`, niente pinch/scroll/pull-to-refresh; unico scroll ammesso è dentro i pannelli della lobby.
- **Prestazioni**: mappa = 1 mesh (colori per vertice) + 1 di contorno; materiali toon a 3 toni; nessuna ombra dinamica (ombre finte); effetti a pool; stato di gioco mutabile fuori da React (HUD a ~12 Hz). **Risoluzione dinamica**: ogni 1.5 s, sotto 48 FPS il pixel ratio scende (min 0.6), sopra 58 risale (max 1.75).
- **Memoria**: ogni geometria/materiale/texture creati a mano viene liberata allo smontaggio (`dispose`), il rendering è fermato e il contesto WebGL rilasciato all'uscita dalla partita; verificato su cicli ripetuti lobby↔partita (heap stabile, nessun avviso di contesti WebGL).
- **Resize/rotazione**: il canvas segue il contenitore (ResizeObserver), la camera delle braccia riallinea l'aspect a ogni frame; in verticale compare l'invito a ruotare.
- **"Multiplayer"**: è una **sessione locale con 6 bot** (stessi 7 personaggi). Un vero online richiede un server WebSocket, che Vercel non ospita: il motore (`sim.js`) è già separato dal rendering, quindi è predisposto per essere portato su un server autoritativo.
