# MangaDSL 言語リファレンス

漫画のコマ割りレイアウトを宣言的に記述するドメイン特化言語（DSL）のリファレンスガイド。

---

## 1. 基本情報

### ファイル拡張子

`.manga`

### 文字エンコーディング

UTF-8

---

## 2. ページ宣言

### 基本構文

```manga
page {
  // ページ属性
  size: A4
  direction: rtl
  gutter: 8
  padding: 20
  background: "#ffffff"
  dpi: 300

  // レイアウト文
  // ...
}
```

### 名前付きページ（オプション）

```manga
page main_layout {
  // ...
}
```

### ページ属性

| 属性 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `size` | `A3` \| `A4` \| `B4` \| `B5` \| `<W>x<H>` | `A4` | ページサイズ |
| `direction` | `rtl` \| `ltr` | `ltr` | 読み順（右→左 or 左→右） |
| `gutter` | number (mm) | `5` | パネル間の隙間 |
| `padding` | number (mm) | `10` | ページ外周マージン |
| `background` | color | `"#ffffff"` | ページ背景色 |
| `dpi` | number | `300` | PNG出力時の解像度 |
| `border` | number (mm) | `1` | 全パネルのデフォルト枠線の太さ |
| `border_color` | color | `"#000000"` | 全パネルのデフォルト枠線色 |

#### サイズ規定値

| サイズ | 幅×高さ (mm) |
|--------|-------------|
| A3 | 297 × 420 |
| A4 | 210 × 297 |
| B4 | 257 × 364 |
| B5 | 182 × 257 |

#### カスタムサイズ指定

```manga
page {
  size: 150x200  // 幅150mm × 高さ200mm
}
```

---

## 3. レイアウト要素

### 3.1 row（行）

縦方向の領域を確保し、その中の子要素を横方向に配置するコンテナ。

#### 基本構文

```manga
row {
  // 子要素（col, panel, row）
}
```

#### 高さ指定

```manga
// 比率指定（親要素の40%）
row height: 40% {
  // ...
}

// 絶対指定（60mm）
row height: 60mm {
  // ...
}

// 省略（残りスペースを均等割り）
row {
  // ...
}

```

#### 属性

| 属性 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `height` | `<n>%` \| `<n>mm` \| 省略 | auto | 高さ |
| `gutter` | number (mm) | 継承 | この階層内のガター |
| `align` | `start` \| `center` \| `end` | `start` | 余白がある場合の配置 |
| `margin_top` | number (mm) | `0` | 上側のマージン |
| `margin_bottom` | number (mm) | `0` | 下側のマージン |
| `margin_left` | number (mm) | `0` | 左側のマージン |
| `margin_right` | number (mm) | `0` | 右側のマージン |

### 3.2 col（列）

横方向の領域を確保し、その中の子要素を縦方向に配置するコンテナ。

#### 基本構文

```manga
col {
  // 子要素（row, panel, col）
}
```

#### 幅指定

```manga
// 比率指定（親要素の30%）
col width: 30% {
  // ...
}

// 絶対指定（50mm）
col width: 50mm {
  // ...
}

// 省略（残りスペースを均等割り）
col {
  // ...
}

```

#### 属性

| 属性 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `width` | `<n>%` \| `<n>mm` \| 省略 | auto | 幅 |
| `gutter` | number (mm) | 継承 | この階層内のガター |
| `align` | `start` \| `center` \| `end` | `start` | 余白がある場合の配置 |
| `margin_top` | number (mm) | `0` | 上側のマージン |
| `margin_bottom` | number (mm) | `0` | 下側のマージン |
| `margin_left` | number (mm) | `0` | 左側のマージン |
| `margin_right` | number (mm) | `0` | 右側のマージン |

### 3.3 panel（パネル）

漫画のコマ（フレーム）を表す葉要素。

#### 基本構文

```manga
// 最小形式
panel my_panel

// 一行属性形式
panel hero importance: 1, border: 2

// ブロック形式
panel quiet {
  importance: 2
  image: "assets/hero.png"
  border: 1
  background: "#f0f0f0"
}
```

#### パネル属性

| 属性 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `importance` | `1` \| `2` \| `3` | `2` | 重要度（1が最重要） |
| `label` | string | なし | パネル内に表示するラベル。省略時は非表示。空文字列 `""` 指定でパネルIDを表示 |
| `image` | string (path) | なし | パネル内画像のパス |
| `image_fit` | `cover` \| `contain` \| `fill` | `cover` | 画像の収め方 |
| `text` | string | なし | パネル内テキスト |
| `text_direction` | `horizontal` \| `vertical` | `horizontal` | 文字方向 |
| `border` | number (mm) | `1` | 枠線の太さ（全辺共通） |
| `border_color` | color | `"#000000"` | 枠線色 |
| `border_top` | number (mm) | `None` | 上辺の枠線の太さ（0=非表示） |
| `border_bottom` | number (mm) | `None` | 下辺の枠線の太さ（0=非表示） |
| `border_left` | number (mm) | `None` | 左辺の枠線の太さ（0=非表示） |
| `border_right` | number (mm) | `None` | 右辺の枠線の太さ（0=非表示） |
| `background` | color | `"#ffffff"` | パネル背景色 |
| `skew_left` | number (度) | `0` | 左辺の罫線の傾斜角度 |
| `skew_right` | number (度) | `0` | 右辺の罫線の傾斜角度 |
| `skew_top` | number (度) | `0` | 上辺の罫線の傾斜角度 |
| `skew_bottom` | number (度) | `0` | 下辺の罫線の傾斜角度 |
| `offset_top` | number (mm) | `0` | 上辺の位置オフセット（負=拡大） |
| `offset_bottom` | number (mm) | `0` | 下辺の位置オフセット（負=拡大） |
| `offset_left` | number (mm) | `0` | 左辺の位置オフセット（負=拡大） |
| `offset_right` | number (mm) | `0` | 右辺の位置オフセット（負=拡大） |

#### 画像の指定

パネル内に画像を配置する場合、`image` 属性で相対パスを指定します。

```manga
panel hero {
  image: "assets/hero.png"
  image_fit: cover
}
```

**パス指定のルール:**
- `.manga` ファイルからの相対パス
- サポート形式: PNG, JPEG, GIF, SVG
- 例: `"./images/scene1.png"`, `"../assets/hero.jpg"`

**image_fit オプション:**
- `cover`: アスペクト比を保ちつつパネル全体を覆う（はみ出た部分は切り取り）
- `contain`: アスペクト比を保ちつつパネル内に収める（余白が生じる可能性あり）
- `fill`: アスペクト比を無視してパネル全体に引き伸ばす

```manga
// カバー（デフォルト）- 画像がパネルを埋め尽くす
panel p1 {
  image: "bg.jpg"
  image_fit: cover
}

// コンテイン - 画像全体が見える
panel p2 {
  image: "character.png"
  image_fit: contain
}

// フィル - 引き伸ばして完全に埋める
panel p3 {
  image: "texture.png"
  image_fit: fill
}
```

#### コマの罫線を斜めにする（躍動感の演出）

パネルの特定の罫線を傾けることで、動きのあるレイアウトを表現できます。

```manga
// 左の罫線を時計回りに10度傾ける
panel action {
  skew_left: 10
}

// 右の罫線を反時計回りに8度傾ける
panel impact {
  skew_right: -8
}

// 左右の罫線を同じ角度で傾ける
panel speed {
  skew_left: 5
  skew_right: 5
}
```

**傾斜角度の方向:**
- 正の値：時計回り
- 負の値：反時計回り
- 各辺（left/right/top/bottom）を個別に指定可能

#### コマの位置をずらす（重なり効果）

パネルの位置をオフセットすることで、隣接するコマに重ねたり、レイアウトグリッドから飛び出す効果を実現できます。実際のマンガでよく使われるダイナミックな表現手法です。

```manga
// 上下に飛び出す迫力のあるコマ
panel impact {
  offset_top: -10     // 上に10mm飛び出す
  offset_bottom: -10  // 下に10mm飛び出す
}

// 右に重なるコマ
panel overlap_right {
  offset_right: -8  // 右のコマに8mm重なる
}

// 左右上下すべてに拡張
panel full_bleed {
  offset_top: -5
  offset_bottom: -5
  offset_left: -5
  offset_right: -5
}

// 内側に縮めることも可能
panel shrink {
  offset_top: 3      // 上から3mm縮む
  offset_left: 3     // 左から3mm縮む
}
```

**オフセット値の意味:**
- **負の値**: パネルが拡大（その方向に飛び出す）
- **正の値**: パネルが縮小（その方向から内側に縮む）
- 単位: mm（ミリメートル）

**使用例:**
- アクションシーンでの迫力ある演出
- 重要なコマを強調（他のコマの上に重ねる）
- ページからはみ出すような大胆な構図
- コマとコマの境界を意図的にずらす

**注意事項:**
- 後に描画されるパネル（下の行、右のコマ）が上に重なります
- 大きすぎるオフセットは隣接するコマを完全に覆い隠す可能性があります

#### 罫線を選択的に省略する（メリハリの演出）

個別の辺ごとに罫線を制御することで、コマの繋がりや流れを表現できます。実際のマンガでよく使われる手法です。

```manga
// 下の罫線を省略して次の行と繋げる
panel flow {
  border_bottom: 0
}

// 上下のみ罫線を表示
panel horizontal_emphasis {
  border_left: 0
  border_right: 0
  border_top: 2
  border_bottom: 2
}

// 左右の罫線を太くして強調
panel vertical_emphasis {
  border_left: 3
  border_right: 3
  border_top: 0
  border_bottom: 0
}

// 完全に罫線なし
panel borderless {
  border_top: 0
  border_bottom: 0
  border_left: 0
  border_right: 0
}
```

**個別罫線制御の優先順位:**
- `border_top`, `border_bottom`, `border_left`, `border_right`が指定されている場合、その値を使用
- 指定がない場合（`None`）、`border`の値を使用
- `0`を指定すると、その辺の罫線が非表示になる

**使用例:**
- 上下のコマを繋げて一体感を出す
- 左右のコマを繋げて連続感を演出
- 重要なコマを罫線で強調（太い罫線）
- 背景コマの罫線を省略（borderless）

---

## 4. コメント

### 単一行コメント

```manga
// これは単一行コメントです
panel hero  // 行末コメントも可能
```

### 複数行コメント

```manga
/*
  これは
  複数行コメント
  です
*/
```

---

## 5. データ型

### 識別子

- パターン: `[a-zA-Z_][a-zA-Z0-9_]*`
- 例: `hero`, `panel_1`, `_temp`

### 数値

- 整数: `40`, `100`
- 小数: `40.5`, `3.14`
- 負数: `-10`, `-5.5`

### 単位付き数値

- mm: `40mm`, `100mm`
- px: `800px`
- pt: `72pt`
- パーセント: `40%`, `50.5%`

### 文字列

- ダブルクォートで囲む: `"hello"`
- エスケープシーケンス:
  - `\"` - ダブルクォート
  - `\\` - バックスラッシュ
  - `\n` - 改行

### 色

- 16進数カラーコード: `"#ff0000"`, `"#rgb"`, `"#rrggbb"`
- 名前付き色: `"red"`, `"blue"`（実装依存）

---

## 6. 使用例

### 例1: シンプルな1パネル

```manga
page {
  panel hero
}
```

### 例2: 2段組

```manga
page {
  gutter: 8

  row height: 60% {
    panel top
  }
  row {
    panel bottom
  }
}
```

### 例3: 4コマ漫画

```manga
page yonkoma {
  size: B5
  direction: rtl
  gutter: 6
  padding: 15

  row height: 25% {
    panel panel1 {
      image: "scenes/scene1.png"
      text: "起"
    }
  }
  row height: 25% {
    panel panel2 {
      image: "scenes/scene2.png"
      text: "承"
    }
  }
  row height: 25% {
    panel panel3 {
      image: "scenes/scene3.png"
      text: "転"
    }
  }
  row {
    panel panel4 {
      image: "scenes/scene4.png"
      text: "結"
      importance: 1
    }
  }
}
```

### 例4: 2×2 グリッド

```manga
page {
  row {
    col { panel p1 }
    col { panel p2 }
  }
  row {
    col { panel p3 }
    col { panel p4 }
  }
}
```

### 例5: 不規則レイアウト

```manga
page action_scene {
  direction: rtl
  gutter: 5

  row height: 60% {
    panel hero {
      importance: 1
      image: "hero_big.png"
    }
  }
  row {
    col { panel detail1 }
    col { panel detail2 }
    col { panel detail3 }
  }
}
```

### 例6: 複雑なネスト

```manga
page complex {
  row height: 50% {
    col width: 60% {
      panel main {
        importance: 1
      }
    }
    col {
      row {
        panel sub1
      }
      row {
        panel sub2
      }
    }
  }
  row {
    col { panel bottom1 }
    col { panel bottom2 }
    col { panel bottom3 }
  }
}
```

### 例7: 画像を使った実践例

```manga
page story {
  size: B5
  gutter: 5

  // 背景画像で雰囲気を出す
  row height: 40% {
    panel establishing_shot {
      image: "backgrounds/city.jpg"
      image_fit: cover
      importance: 1
    }
  }

  // キャラクター中心のコマ
  row height: 30% {
    col {
      panel char1 {
        image: "characters/hero.png"
        image_fit: contain
        border: 2
      }
    }
    col {
      panel char2 {
        image: "characters/rival.png"
        image_fit: contain
        border: 2
      }
    }
  }

  // リアクションコマ
  row {
    panel reaction {
      image: "effects/surprise.png"
      image_fit: cover
    }
  }
}
```

### 例8: 躍動感のあるレイアウト（skew使用）

```manga
page action {
  gutter: 6

  // 上段: 左右の辺を傾けて平行四辺形に
  row height: 40% {
    panel impact {
      importance: 1
      skew_left: 8
      skew_right: 8
    }
  }

  // 中段: 各コマを逆方向に傾ける
  row height: 30% {
    col {
      panel reaction1 {
        skew_right: -5
      }
    }
    col {
      panel reaction2 {
        skew_left: -5
      }
    }
  }

  // 下段: 通常配置
  row {
    panel aftermath
  }
}
```

---

## 7. ベストプラクティス

### 命名規則

- パネルIDは内容を表す名前を使う: `hero`, `villain`, `background`
- ページ名は用途を表す: `main_layout`, `title_page`

### レイアウト設計

1. まず大枠を `row` で縦分割
2. 必要に応じて `col` で横分割
3. サイズ指定は重要度の高いパネルから順に
4. `%` 指定を多用しすぎない（auto を活用）
5. **躍動感の演出**: アクションシーンでは `skew` を使用してコマを傾ける（推奨: -10度〜+10度）

### 画像の使い方

1. **ディレクトリ構成**: 画像は専用フォルダにまとめる（例: `images/`, `assets/`）
2. **image_fitの選択**:
   - 背景・風景 → `cover`（画面を埋め尽くす）
   - キャラクター・オブジェクト → `contain`（全体を見せる）
   - テクスチャ・パターン → `fill`（引き伸ばす）
3. **ファイルサイズ**: 大きすぎる画像は避ける（推奨: 2MB以下）
4. **形式**: PNG（透過対応）、JPEG（写真）、SVG（ベクター）を使い分ける

### 可読性

- 適切なインデントを使用（2スペースまたは4スペース）
- セクションごとにコメントを追加
- 長いファイルは空行で区切る

---

## 8. よくあるエラー

### 構文エラー

```
Parse error: Unexpected token at line 10, column 5
Expected one of: row, col, panel
```

→ 構文が間違っています。波括弧やコロンの位置を確認してください。

### 比率超過エラー

```
Layout error: Percentage total (110%) exceeds 100%
```

→ 同じ階層内の `%` 指定の合計が100%を超えています。

### パネルID重複エラー

```
Validation error: Duplicate panel ID 'hero'
```

→ 同じIDのパネルが複数定義されています。一意なIDを使用してください。

### 画像ファイルエラー

```
Warning: Image file not found: 'assets/hero.png'
```

→ 指定された画像ファイルが見つかりません。パスが正しいか確認してください。

```
Error: Unsupported image format: 'image.bmp'
```

→ サポートされていない画像形式です。PNG、JPEG、GIF、SVGを使用してください。

---

**MangaDSL Language Reference v1.0**
最終更新: 2026-06-12
