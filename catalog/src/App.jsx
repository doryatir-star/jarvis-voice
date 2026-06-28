import { useMemo, useState } from 'react'
import { categories, allProducts, coupons } from './products.js'

const shekel = (n) => `${n} ₪`

export default function App() {
  // עגלה: מפה של מזהה מוצר -> כמות
  const [cart, setCart] = useState({})
  const [query, setQuery] = useState('')
  const [couponInput, setCouponInput] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState(null)
  const [couponError, setCouponError] = useState('')

  const addToCart = (id) =>
    setCart((c) => ({ ...c, [id]: (c[id] || 0) + 1 }))

  const decFromCart = (id) =>
    setCart((c) => {
      const next = { ...c }
      if (!next[id]) return next
      next[id] -= 1
      if (next[id] <= 0) delete next[id]
      return next
    })

  const removeFromCart = (id) =>
    setCart((c) => {
      const next = { ...c }
      delete next[id]
      return next
    })

  const cartItems = useMemo(
    () =>
      Object.entries(cart).map(([id, qty]) => ({
        ...allProducts.find((p) => p.id === id),
        qty,
      })),
    [cart],
  )

  const itemCount = cartItems.reduce((sum, it) => sum + it.qty, 0)
  const subtotal = cartItems.reduce((sum, it) => sum + it.price * it.qty, 0)

  // ההנחה לעולם לא תוריד את הסכום מתחת ל-0
  const discount = appliedCoupon
    ? Math.min(appliedCoupon.discount, subtotal)
    : 0
  const total = subtotal - discount

  const applyCoupon = (e) => {
    e.preventDefault()
    const code = couponInput.trim().toUpperCase()
    const found = coupons[code]
    if (!found) {
      setCouponError('קוד קופון לא תקין')
      setAppliedCoupon(null)
      return
    }
    setCouponError('')
    setAppliedCoupon(found)
  }

  const clearCoupon = () => {
    setAppliedCoupon(null)
    setCouponInput('')
    setCouponError('')
  }

  const normalizedQuery = query.trim()

  return (
    <div className="page">
      <header className="header">
        <div className="brand">
          <span className="brand-emoji">🛍️</span>
          <div>
            <h1>החנות שלנו</h1>
            <p>כל המוצרים שלנו במקום אחד — מסודר, נוח ומשתלם</p>
          </div>
        </div>
        <div className="header-tools">
          <input
            className="search"
            type="search"
            placeholder="חיפוש מוצר…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="חיפוש מוצר"
          />
          <div className="cart-badge" title="פריטים בעגלה">
            🛒 <span>{itemCount}</span>
          </div>
        </div>
      </header>

      <div className="layout">
        <main className="catalog">
          {categories.map((cat) => {
            const visible = cat.products.filter((p) =>
              p.name.includes(normalizedQuery),
            )
            if (visible.length === 0) return null
            return (
              <section key={cat.id} className="category">
                <div className="category-head">
                  <h2>
                    <span>{cat.emoji}</span> {cat.title}
                  </h2>
                  {cat.note && <span className="category-note">{cat.note}</span>}
                </div>
                <div className="grid">
                  {visible.map((p) => (
                    <article key={p.id} className="card">
                      <div className="card-emoji">{p.emoji}</div>
                      <h3 className="card-name">{p.name}</h3>
                      <div className="card-foot">
                        <span className="price">{shekel(p.price)}</span>
                        <button className="add-btn" onClick={() => addToCart(p.id)}>
                          הוסף לעגלה
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )
          })}
          {allProducts.filter((p) => p.name.includes(normalizedQuery)).length ===
            0 && <p className="empty">לא נמצאו מוצרים התואמים לחיפוש.</p>}
        </main>

        <aside className="cart">
          <h2>העגלה שלי</h2>
          {cartItems.length === 0 ? (
            <p className="cart-empty">העגלה ריקה. הוסיפו מוצרים מהקטלוג 🙂</p>
          ) : (
            <>
              <ul className="cart-list">
                {cartItems.map((it) => (
                  <li key={it.id} className="cart-row">
                    <div className="cart-info">
                      <span className="cart-emoji">{it.emoji}</span>
                      <div>
                        <div className="cart-name">{it.name}</div>
                        <div className="cart-unit">{shekel(it.price)} ליחידה</div>
                      </div>
                    </div>
                    <div className="qty">
                      <button onClick={() => decFromCart(it.id)} aria-label="הפחת">
                        −
                      </button>
                      <span>{it.qty}</span>
                      <button onClick={() => addToCart(it.id)} aria-label="הוסף">
                        +
                      </button>
                    </div>
                    <div className="cart-line">{shekel(it.price * it.qty)}</div>
                    <button
                      className="remove"
                      onClick={() => removeFromCart(it.id)}
                      aria-label="הסר"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>

              <form className="coupon" onSubmit={applyCoupon}>
                <label htmlFor="coupon">יש לכם קופון?</label>
                <div className="coupon-row">
                  <input
                    id="coupon"
                    type="text"
                    placeholder="הקלידו קוד קופון"
                    value={couponInput}
                    onChange={(e) => setCouponInput(e.target.value)}
                  />
                  <button type="submit">החל</button>
                </div>
                {couponError && <p className="coupon-error">{couponError}</p>}
                {appliedCoupon && (
                  <p className="coupon-ok">
                    הקופון <strong>{appliedCoupon.code}</strong> הופעל —{' '}
                    {appliedCoupon.label}{' '}
                    <button type="button" className="link" onClick={clearCoupon}>
                      הסר
                    </button>
                  </p>
                )}
                <p className="coupon-hint">טיפ: נסו את הקוד <code>SAVE15</code></p>
              </form>

              <div className="summary">
                <div className="summary-row">
                  <span>סכום ביניים</span>
                  <span>{shekel(subtotal)}</span>
                </div>
                {discount > 0 && (
                  <div className="summary-row discount">
                    <span>הנחת קופון</span>
                    <span>−{shekel(discount)}</span>
                  </div>
                )}
                <div className="summary-row total">
                  <span>סה״כ לתשלום</span>
                  <span>{shekel(total)}</span>
                </div>
              </div>

              <button className="checkout">מעבר לתשלום</button>
            </>
          )}
        </aside>
      </div>

      <footer className="footer">
        <p>נבנה באהבה • כל המחירים בשקלים חדשים</p>
      </footer>
    </div>
  )
}
