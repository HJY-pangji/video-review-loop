"""편집 엔진: 장면 목록(대본)을 받아 영상으로 만든다.

원칙
  1. 말이 있는 곳은 실제 목소리 + 받아쓰기 자막
  2. 말이 없는 곳만 해설 자막
  3. 시끄러운 엔진음은 줄이고 음악
자막: 한 줄, 최대 16자, 노출 시간 >= 글자 수/12초, 최소 1초

장면(dict) 키
  src, ss, dur        원본 파일, 시작 초, 길이(0.1초 단위로 쓸 것)
  mode                'voice'(말소리: 잡음 제거 + 음량 자동) | 'noise'(엔진음: 크게 줄임) | 'amb'(현장음 -9dB) | 'mute'(원음 제거)
  caps                자막. 문자열 목록이면 자동 배치, (글, 시작, 끝) 튜플이면 그 시각에 표시(말 자막용)
  music               이 장면부터 깔 음악 이름('off'면 끔). assets/music/<이름>.wav
  badge, title        왼쪽 위 배지, 타이틀(큰 글, 작은 글)
  card / endcard      (작은 글, 큰 글) 글자만 있는 화면
  split, labels       (왼쪽 파일, 시작, 오른쪽 파일, 시작) 좌우 비교 화면
  crop, pre           (x, y, w, h) 잘라 쓰기 / 화면 필터 앞에 붙일 ffmpeg 필터(예: 'transpose=2,')
  hp, dn, dnmix       말소리 저역 차단 Hz(기본 90) / 잡음 제거 모델 'bd'|'cb' / 제거 비율(기본 0.9, 시끄러운 곳은 1.0)
  ambdb               'amb' 장면 원음 크기 dB (기본 -9)
  fadein, fadeout     화면 페이드
"""
import json, os, re, shutil, sys
import numpy as np
from . import draw
from .paths import MUSIC, REVIEW, RNN, out_dir, run

W, H = draw.W, draw.H
CPS, MAXLEN, MINDUR, MINSHOW, EXTRA = 12, 16, 1.0, 2.6, 1.4
MVOL = {'voice': 0.09, 'noise': 0.30, 'amb': 0.24, 'mute': 0.34, 'card': 0.26}   # 장면 종류별 음악 크기
VOICE_TARGET, GMIN, GMAX = -14.0, -8.0, 32.0                                      # 말소리 목표 크기(dB)와 보정 한도
FINAL_LUFS = -15.0
BG = '0x0b1622'


class Episode:
    def __init__(self, name, version, scenes, chapters=(), crf='23', handle=''):
        # handle: 엔딩 화면 아래에 넣을 채널 표기 (예: '채널명 @example'). 비우면 표시하지 않는다.
        self.name, self.version, self.S, self.chapters, self.handle = name, version, scenes, list(chapters), handle
        self.out = out_dir(name); self.aud = self.out + 'aud/'; os.makedirs(self.aud, exist_ok=True)
        self.enc = ['-c:v', 'libx264', '-crf', os.environ.get('CRF', crf), '-preset', 'faster', '-r', '30', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']
        self.final = f'{self.out}{name}_{version}_1080p.mp4'
        self.srt = f'{self.out}{name}_{version}_1080p.srt'
        self._mlen = {}

    # ── 자막 배치와 검사
    def windows(self, sc):
        caps = sc.get('caps', []); d = sc['dur']
        if not caps: return []
        if isinstance(caps[0], tuple): return list(caps)
        n = len(caps); seg = d / n; out = []
        for k, c in enumerate(caps):
            need = max(MINDUR, len(c) / CPS)
            show = min(seg - 0.15, max(MINSHOW, need + EXTRA)) if n > 1 else min(d - 0.2, max(MINSHOW, need + EXTRA, d * 0.7))
            a = k * seg + (0.3 if k == 0 and d > 6 else 0.1)
            out.append((c, a, min(a + show, d)))
        return out

    def check(self):
        ok = True
        for i, sc in enumerate(self.S):
            if abs(sc['dur'] * 30 - round(sc['dur'] * 30)) > 1e-6:
                ok = False; print(f'FAIL S{i:02d} 길이 {sc["dur"]}초가 프레임 단위(1/30초)에 맞지 않습니다')
            for c, a, b in self.windows(sc):
                need = max(MINDUR, len(c) / CPS)
                if len(c) > MAXLEN or (b - a) < need or b > sc['dur'] + 0.01:
                    ok = False; print(f'FAIL S{i:02d} {len(c)}자 {b-a:.2f}/{need:.2f}s {c}')
        return ok

    # ── 소리 계획
    def vpre(self, sc):
        return f"highpass=f={sc.get('hp', 90)},arnndn=m={RNN[sc.get('dn', 'bd')]}:mix={sc.get('dnmix', 0.9)}"

    def plan_gain(self):
        """목소리 장면마다 말소리 크기(0.25초 단위 상위 5%)를 재서 같은 크기로 맞춘다"""
        cf = self.out + 'gain.json'
        cache = json.load(open(cf, encoding='utf-8')) if os.path.exists(cf) else {}
        for sc in self.S:
            if sc.get('mode') != 'voice': continue
            key = f"{os.path.basename(sc['src'])[:30]}|{sc['ss']}|{sc['dur']}|{self.vpre(sc)[-40:]}"
            if key not in cache:
                raw = run(['ffmpeg', '-v', 'error', '-ss', str(sc['ss']), '-t', str(sc['dur']), '-i', sc['src'], '-vn',
                           '-af', 'aresample=48000,' + self.vpre(sc) + ',highpass=f=200,lowpass=f=3500', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                          capture_output=True).stdout
                a = np.frombuffer(raw, dtype=np.float32); n = 4000
                if len(a) < n * 2: sys.exit(f'소리를 읽지 못했습니다: {sc["src"]}')
                v = [20 * np.log10(np.sqrt((a[i:i + n] ** 2).mean()) + 1e-9) for i in range(0, len(a) - n, n)]
                cache[key] = float(np.percentile(v, 95))
            sc['_p95'] = cache[key]; sc['_g'] = float(min(GMAX, max(GMIN, VOICE_TARGET - cache[key])))
        json.dump(cache, open(cf, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    def music_len(self, trk):
        if trk not in self._mlen:
            r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(MUSIC / f'{trk}.wav')], capture_output=True, text=True)
            if r.returncode or not r.stdout.strip(): sys.exit(f'음악 파일이 없습니다: assets/music/{trk}.wav')
            self._mlen[trk] = float(r.stdout.strip())
        return self._mlen[trk]

    def plan_music(self):
        cur, pos, prev = 'off', 0.0, 0.0
        for sc in self.S:
            if sc.get('music'): cur, pos = sc['music'], 0.0
            mode = 'card' if (sc.get('card') or sc.get('endcard')) else ('mute' if sc.get('split') else sc['mode'])
            lvl = 0.0 if cur == 'off' else MVOL[mode]
            sc['_m'] = (cur, pos % (self.music_len(cur) if cur != 'off' else 1), prev, lvl)
            prev = lvl; pos += sc['dur']

    def music_in(self, sc):
        trk, pos, prev, lvl = sc['_m']; d = sc['dur']
        if trk == 'off':
            return ['-f', 'lavfi', '-t', str(d), '-i', 'anullsrc=r=48000:cl=stereo'], 'anull'
        vol = f"volume='if(lt(t,0.5),{prev}+({lvl}-{prev})*t/0.5,{lvl})':eval=frame"
        return ['-stream_loop', '-1', '-ss', f'{pos:.3f}', '-t', str(d), '-i', str(MUSIC / f'{trk}.wav')], vol

    def orig_af(self, sc):
        d = sc['dur']; m = sc['mode']; fade = f'afade=t=in:d=0.12,afade=t=out:st={d-0.15}:d=0.15'
        pre = 'aresample=48000,aformat=channel_layouts=stereo,'
        if m == 'voice':
            return pre + f"{self.vpre(sc)},volume={sc['_g']:.1f}dB,acompressor=threshold=0.1:ratio=3:attack=5:release=150,alimiter=limit=0.7:level=false,{fade}"
        if m == 'noise': return pre + f'highpass=f=150,lowpass=f=3000,volume=-27dB,{fade}'
        if m == 'amb': return pre + f"volume={sc.get('ambdb', -9)}dB,{fade}"
        return pre + 'volume=0'

    # ── 장면 하나 렌더링 (화면 + 자막 + 임시 소리)
    def render(self, i, sc):
        OUT = self.out; d = sc['dur']; tmp, dst = f'{OUT}s{i:02d}.tmp.mp4', f'{OUT}s{i:02d}.mp4'
        mi, mvol = self.music_in(sc)
        if sc.get('card') or sc.get('endcard'):
            p = f'{OUT}ov{i:02d}.png'
            if sc.get('endcard'): draw.overlay(p, endcard=sc['endcard'], handle=self.handle)
            else: draw.card(p, *sc['card'])
            fo = 1.2 if sc.get('endcard') else 0.5
            cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={BG}:s={W}x{H}:r=30:d={d}',
                   '-loop', '1', '-t', str(d), '-i', p, *mi, '-filter_complex',
                   f'[0:v][1:v]overlay,fade=t=in:d=0.4,fade=t=out:st={d-fo}:d={fo}[v];[2:a]{mvol}' + (f',afade=t=out:st={d-1.5}:d=1.5' if sc.get('endcard') else '') + '[a]',
                   '-map', '[v]', '-map', '[a]', '-t', str(d), *self.enc, tmp]
        elif sc.get('split'):
            l, ls, r, rs = sc['split']
            ins = ['-ss', str(ls), '-t', str(d), '-i', l, '-ss', str(rs), '-t', str(d), '-i', r]
            fc = (f'color=c={BG}:s={W}x{H}:r=30:d={d}[bg];[0:v]scale=-2:960,setsar=1[l];[1:v]scale=-2:960,setsar=1[r];'
                  f'[bg][l]overlay=340:30[t];[t][r]overlay=1040:30[base]'); last = 'base'
            wins = self.windows(sc) or [(None, 0, d)]
            for k, (c, a, b) in enumerate(wins):
                p = f'{OUT}ov{i:02d}_{k}.png'; draw.split_labels(p, sc['labels'], c)
                ins += ['-loop', '1', '-t', str(d), '-i', p]
                fc += f";[{last}][{k+2}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[o{k}]"; last = f'o{k}'
            p0 = f'{OUT}ov{i:02d}_L.png'; draw.split_labels(p0, sc['labels'], None)     # 자막 사이에도 라벨이 보이게
            ins += ['-loop', '1', '-t', str(d), '-i', p0]; nL = len(wins) + 2
            fc += f';[{last}][{nL}:v]overlay=0:0,fps=30,format=yuv420p[v]'
            cmd = ['ffmpeg', '-v', 'error', '-y', *ins, *mi, '-filter_complex', fc + f';[{nL+1}:a]{mvol}[a]',
                   '-map', '[v]', '-map', '[a]', '-t', str(d), *self.enc, tmp]
        else:
            ins = ['-ss', str(sc['ss']), '-t', str(d), '-i', sc['src']]
            if sc.get('crop'):
                x, y, w, h = sc['crop']; fc = f'[0:v]crop={w}:{h}:{x}:{y},scale={W}:{H},setsar=1[base]'
            elif sc.get('pre'):
                fc = f"[0:v]{sc['pre']}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[base]"
            else: fc = draw.base(sc['src'])
            last = 'base'; layers = list(self.windows(sc))
            if sc.get('title') or sc.get('badge'): layers.append((None, 0, d + 1))
            for k, (c, a, b) in enumerate(layers):
                p = f'{OUT}ov{i:02d}_{k}.png'
                draw.overlay(p, cap=c, title=sc.get('title') if c is None else None, badge=sc.get('badge') if c is None else None)
                ins += ['-loop', '1', '-t', str(d), '-i', p]
                fc += f";[{last}][{k+1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[o{k}]"; last = f'o{k}'
            tail = (',fade=t=in:d=0.6' if sc.get('fadein') else '') + (f',fade=t=out:st={d-1.0}:d=1.0' if sc.get('fadeout') else '')
            fc += f';[{last}]fps=30,format=yuv420p{tail}[v]'
            nm = len(layers) + 1
            fc += f';[0:a]{self.orig_af(sc)}[oa];[{nm}:a]{mvol}[ma];[oa][ma]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]'
            cmd = ['ffmpeg', '-v', 'error', '-y', *ins, *mi, '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-t', str(d), *self.enc, tmp]
        if run(cmd).returncode: sys.exit(f'장면 {i} 렌더링 실패')
        os.replace(tmp, dst)

    # ── 자막 파일, 챕터, 실제 목소리 목록
    def meta(self):
        t0 = 0; n = 1; lines = []; ch = [(0, '오프닝')]; lastb = None; voice = []
        for sc in self.S:
            bd = sc.get('badge')
            if bd in self.chapters and bd != lastb and t0 > 9: ch.append((t0, bd.replace('  ', ' '))); lastb = bd
            for c, a, b in self.windows(sc):
                lines.append(f'{n}\n{draw.ts(t0+a)} --> {draw.ts(t0+b)}\n{c}\n'); n += 1
                if sc.get('mode') == 'voice' and not c.startswith('('): voice.append(f'{int((t0+a)//60)}:{int((t0+a)%60):02d}  {c}')
            t0 += sc['dur']
        open(self.srt, 'w', encoding='utf-8').write('\n'.join(lines))
        open(self.out + 'chapters.txt', 'w', encoding='utf-8').write('\n'.join(f'{int(t//60)}:{int(t%60):02d} {b}' for t, b in ch))
        open(self.out + 'voice_caps.txt', 'w', encoding='utf-8').write('\n'.join(voice))
        return t0

    def timeline(self):
        """장면 번호 ↔ 완성본 시각 표. 리뷰 메모의 시각으로 장면을 찾을 때 쓴다."""
        t = 0; rows = []
        for i, sc in enumerate(self.S):
            kind = 'card' if (sc.get('card') or sc.get('endcard')) else ('split' if sc.get('split') else sc['mode'])
            caps = ' / '.join(c for c, _, _ in self.windows(sc)) or (sc.get('card') or sc.get('endcard') or ('',))[-1]
            rows.append(f'S{i:02d}  {int(t//60)}:{t%60:04.1f}  {sc["dur"]:5.1f}s  {kind:5s}  {caps}'); t += sc['dur']
        open(self.out + 'timeline.txt', 'w', encoding='utf-8').write('\n'.join(rows))
        return rows

    def scene_at(self, t):
        t0 = 0
        for i, sc in enumerate(self.S):
            if t0 <= t < t0 + sc['dur']: return i, t - t0
            t0 += sc['dur']
        return len(self.S) - 1, 0

    # ── 이어 붙이기
    def join(self):
        missing = [i for i in range(len(self.S)) if not os.path.exists(f'{self.out}s{i:02d}.mp4')]
        if missing: sys.exit(f'아직 렌더링하지 않은 장면: {missing}')
        open(self.out + 'list.txt', 'w', encoding='utf-8').write(''.join(f"file 's{i:02d}.mp4'\n" for i in range(len(self.S))))
        run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', self.out + 'list.txt', '-c', 'copy', self.out + 'joined.mp4'], check=True)

    # ── 최종 소리: 장면별 WAV → 이어 붙이기 → 전체 음량 맞춤 → 화면과 합치기 (소리만 고칠 때는 이것만 다시)
    def mix(self, only=()):
        A = self.aud
        for i, sc in enumerate(self.S):
            dst = f'{A}a{i:02d}.wav'
            if only and i not in only and os.path.exists(dst): continue
            d = sc['dur']; mi, mvol = self.music_in(sc)
            if sc.get('card') or sc.get('endcard') or sc.get('split'):
                fc = f'[0:a]{mvol}' + (f',afade=t=out:st={d-1.5}:d=1.5' if sc.get('endcard') else '') + ',aresample=48000,aformat=channel_layouts=stereo[a]'
                cmd = ['ffmpeg', '-v', 'error', '-y', *mi, '-filter_complex', fc, '-map', '[a]', '-t', str(d), '-c:a', 'pcm_s16le', dst]
            else:
                fc = (f'[0:a]{self.orig_af(sc)}[oa];[1:a]{mvol},aresample=48000,aformat=channel_layouts=stereo[ma];'
                      f'[oa][ma]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95:level=false,apad[a]')
                cmd = ['ffmpeg', '-v', 'error', '-y', '-vn', '-ss', str(sc['ss']), '-t', str(d), '-i', sc['src'], *mi,
                       '-filter_complex', fc, '-map', '[a]', '-t', str(d), '-c:a', 'pcm_s16le', dst]
            if run(cmd).returncode: sys.exit(f'장면 {i} 소리 처리 실패')
        open(A + 'list.txt', 'w', encoding='utf-8').write(''.join(f"file 'a{i:02d}.wav'\n" for i in range(len(self.S))))
        run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', A + 'list.txt', '-c', 'copy', A + 'mix.wav'], check=True)
        I, lra, pk = loudness(A + 'mix.wav'); g = FINAL_LUFS - I
        print(f'섞은 결과 {I} LUFS, 피크 {pk} dB → {g:+.1f}dB', flush=True)
        run(['ffmpeg', '-v', 'error', '-y', '-i', A + 'mix.wav', '-af', f'volume={g:.2f}dB,alimiter=limit=0.78:level=false:attack=3:release=80',
             '-c:a', 'pcm_s16le', A + 'final.wav'], check=True)
        I2, lra2, pk2 = loudness(A + 'final.wav'); print(f'최종 {I2} LUFS, 음량 폭 {lra2} LU, 피크 {pk2} dB', flush=True)
        tmp = self.out + 'final.tmp.mp4'
        run(['ffmpeg', '-v', 'error', '-y', '-i', self.out + 'joined.mp4', '-i', A + 'final.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', tmp], check=True)
        os.replace(tmp, self.final); print('완성:', self.final, flush=True)

    def publish(self):
        """완성본과 자막을 리뷰 폴더의 컨펌본으로 복사"""
        if not REVIEW: return print('config.json에 review_dir이 없어 컨펌본 복사를 건너뜁니다')
        dst = REVIEW / '컨펌본'; dst.mkdir(parents=True, exist_ok=True)
        for f in (self.final, self.srt): shutil.copy2(f, dst / os.path.basename(f))
        print('컨펌본에 복사:', dst / os.path.basename(self.final))

    # ── 명령줄
    def main(self, argv=None):
        argv = sys.argv[1:] if argv is None else argv
        if not self.check(): sys.exit('자막 기준 미달')
        total = self.meta(); rows = self.timeline()
        print(f'{self.name} {self.version}: 총 길이 {total:.1f}초 = {int(total//60)}분 {int(total%60)}초, 장면 {len(self.S)}개', flush=True)
        if 'check' in argv and 'gain' not in argv: return
        if 'timeline' in argv: return print('\n'.join(rows))
        if 'at' in argv:
            t = argv[argv.index('at') + 1]; sec = sum(float(x) * 60 ** k for k, x in enumerate(reversed(t.split(':'))))
            i, off = self.scene_at(sec); return print(f'{t} → 장면 S{i:02d}, 장면 안에서 {off:.1f}초 지점\n{rows[i]}')
        self.plan_gain(); self.plan_music()
        if 'check' in argv:
            for i, sc in enumerate(self.S):
                if sc.get('mode') == 'voice': print(f"  S{i:02d} 말소리 {sc['_p95']:.1f}dB → {sc['_g']:+.1f}dB")
            return
        pub = 'publish' in argv; args = [a for a in argv if a != 'publish']
        if pub and not args: return self.publish()                 # publish만 쓰면 복사만
        only = [int(a) for a in args if a.isdigit()]; audio = 'audio' in args
        if not audio:
            for i, sc in enumerate(self.S):
                if only and i not in only: continue
                self.render(i, sc); print('장면 완료', i, flush=True)
        if audio or not only or 'join' in args:
            if not audio or not os.path.exists(self.out + 'joined.mp4'): self.join()
            self.mix(only=only if audio else ())
            if pub: self.publish()


def loudness(f):
    r = run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    return (float(re.findall(r'I:\s+(-?[0-9.]+) LUFS', r)[-1]), float(re.findall(r'LRA:\s+(-?[0-9.]+) LU', r)[-1]), float(re.findall(r'Peak:\s+(-?[0-9.]+) dBFS', r)[-1]))
