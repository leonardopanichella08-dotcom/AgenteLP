import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import LobbyUI from './components/LobbyUI.jsx';
import GameUI from './components/GameUI.jsx';
import EndScreen from './components/EndScreen.jsx';
import { getCharacter } from './game/characters.js';
import { createMatch } from './game/sim.js';
import { input, resetInput } from './game/input.js';

// three.js è pesante: viene scaricato solo quando parte la partita (lobby istantanea).
const Scene3D = lazy(() => import('./scene/Scene3D.jsx'));

const BASE_SENS = 0.0055;
const store = {
  get(k, d) { try { return window.localStorage.getItem(`aula.${k}`) ?? d; } catch { return d; } },
  set(k, v) { try { window.localStorage.setItem(`aula.${k}`, v); } catch { /* storage non disponibile */ } },
};
const params = new URLSearchParams(window.location.search);
const FORCE_TOUCH = params.get('touch') === '1';
const DEBUG = params.get('debug') === '1';
const EVENT_DELAY = params.get('event') ? Number(params.get('event')) : undefined; // debug: ?event=8

const detectTouch = () =>
  FORCE_TOUCH || window.matchMedia?.('(pointer: coarse)').matches || navigator.maxTouchPoints > 0;

export default function App() {
  const [screen, setScreen] = useState('lobby'); // lobby | match | over
  const [charId, setCharId] = useState(() => store.get('char', 'leonardo'));
  const [loadoutId, setLoadoutId] = useState(() => getCharacter(store.get('char', 'leonardo')).loadout);
  const [result, setResult] = useState(null);
  const [paused, setPaused] = useState(false);
  const [matchKey, setMatchKey] = useState(0);
  const [sens, setSens] = useState(() => Number(store.get('sens', '1')) || 1);
  const [isTouch] = useState(detectTouch);
  const stateRef = useRef(null);
  const pausedRef = useRef(false);
  if (DEBUG) window.__aula = { get state() { return stateRef.current; }, input };

  useEffect(() => { input.sens = BASE_SENS * sens * (isTouch ? 1 : 0.45); }, [sens, isTouch]);

  const selectChar = (id) => {
    setCharId(id); setLoadoutId(getCharacter(id).loadout); store.set('char', id);
  };

  const start = useCallback(() => {
    resetInput();
    stateRef.current = createMatch({ charId, loadoutId, eventDelay: EVENT_DELAY });
    pausedRef.current = false;
    setPaused(false); setResult(null);
    setMatchKey((k) => k + 1);
    setScreen('match');
  }, [charId, loadoutId]);

  const setPause = useCallback((v) => { pausedRef.current = v; setPaused(v); if (v) resetInput(); }, []);
  const quit = useCallback(() => { resetInput(); setPause(false); stateRef.current = null; setScreen('lobby'); }, [setPause]);
  const onOver = useCallback((res) => { resetInput(); setResult(res); setScreen('over'); }, []);

  // pausa automatica se la pagina va in background
  useEffect(() => {
    const onHide = () => { if (document.hidden && screen === 'match') setPause(true); };
    document.addEventListener('visibilitychange', onHide);
    return () => document.removeEventListener('visibilitychange', onHide);
  }, [screen, setPause]);

  // schermo sempre acceso durante la partita
  useEffect(() => {
    if (screen !== 'match' || !navigator.wakeLock) return undefined;
    let lock = null;
    navigator.wakeLock.request('screen').then((l) => { lock = l; }).catch(() => {});
    return () => { lock?.release().catch(() => {}); };
  }, [screen]);

  const fullscreen = async () => {
    try {
      await document.documentElement.requestFullscreen?.({ navigationUI: 'hide' });
      await window.screen.orientation?.lock?.('landscape');
    } catch { /* non supportato (es. iOS): si gioca comunque */ }
  };

  const onSens = (v) => { setSens(v); store.set('sens', String(v)); };

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#1b1f3b]">
      {screen === 'lobby' && (
        <LobbyUI
          charId={charId} loadoutId={loadoutId}
          onSelectChar={selectChar} onSelectLoadout={setLoadoutId}
          onPlay={() => { start(); }} onFullscreen={fullscreen}
        />
      )}
      {screen !== 'lobby' && stateRef.current && (
        <>
          <Suspense fallback={<div className="absolute inset-0 flex items-center justify-center font-display text-xl font-black">Caricamento aula…</div>}>
            <Scene3D key={matchKey} stateRef={stateRef} input={input} pausedRef={pausedRef} onOver={onOver} />
          </Suspense>
          <GameUI
            stateRef={stateRef} input={input} pausedRef={pausedRef} paused={paused} isTouch={isTouch}
            onPause={() => setPause(true)} onResume={() => setPause(false)} onQuit={quit}
            sens={sens} onSens={onSens}
          />
        </>
      )}
      {screen === 'over' && result && <EndScreen result={result} onAgain={start} onLobby={quit} />}
    </div>
  );
}
