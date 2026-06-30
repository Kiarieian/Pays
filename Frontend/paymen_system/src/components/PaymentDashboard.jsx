import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Smartphone,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  Receipt,
  Clock,
  Wifi,
  Battery,
  Signal,
} from "lucide-react";
import api, { ApiError } from "../Api/api";

/* ------------------------------------------------------------------
   KIARIE PAY — STK Push Dashboard
   Design language: Safaricom green, USSD/dial-pad inspired "signature"
   element — a live simulated phone screen that types out the actual
   STK push prompt the customer sees, dot-matrix style.
------------------------------------------------------------------- */

const GREEN = "#00A651";
const GREEN_DARK = "#067C3D";
const LIME = "#9AE600";

function classNames(...c) {
  return c.filter(Boolean).join(" ");
}

/* ---------------------------- Phone Mockup ---------------------------- */

function PhoneScreen({ stage, phone, amount, receipt }) {
  // stage: idle | dialing | prompt | typing-pin | confirming | success | failed
  const promptText = `M-PESA\nConfirm to pay\nKSh ${amount || "0"}\nto KIARIE STR\n\nEnter PIN:`;
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (stage !== "prompt") {
      setTyped("");
      return;
    }
    let i = 0;
    const t = setInterval(() => {
      i++;
      setTyped(promptText.slice(0, i));
      if (i >= promptText.length) clearInterval(t);
    }, 18);
    return () => clearInterval(t);
  }, [stage]); // eslint-disable-line

  return (
    <div className="relative w-[260px] sm:w-[280px] mx-auto select-none">
      {/* phone body */}
      <div
        className="rounded-[2.2rem] p-3 shadow-2xl"
        style={{
          background: "linear-gradient(160deg,#1a1f1c,#0c0f0d)",
          boxShadow: "0 30px 60px -15px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
        }}
      >
        <div className="rounded-[1.6rem] overflow-hidden bg-black relative" style={{ aspectRatio: "9/18.5" }}>
          {/* status bar */}
          <div className="flex items-center justify-between px-4 pt-2 text-[10px] text-white/70 font-mono">
            <span>9:41</span>
            <div className="flex items-center gap-1">
              <Signal size={10} />
              <Wifi size={10} />
              <Battery size={11} />
            </div>
          </div>

          {/* notch */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-20 h-4 bg-black rounded-b-xl z-10" />

          {/* screen content */}
          <div className="h-full w-full flex items-center justify-center px-4 pb-8 pt-6">
            {stage === "idle" && (
              <div className="text-center">
                <div
                  className="w-14 h-14 rounded-2xl mx-auto mb-3 flex items-center justify-center animate-pulse"
                  style={{ background: `${GREEN}22` }}
                >
                  <Smartphone size={24} color={GREEN} />
                </div>
                <p className="text-white/40 text-[11px] font-mono">Waiting to send request…</p>
              </div>
            )}

            {stage === "dialing" && (
              <div className="text-center">
                <Loader2 className="animate-spin mx-auto mb-3" size={28} color={GREEN} />
                <p className="text-white text-[11px] font-mono">
                  Sending push to <br />
                  <span style={{ color: GREEN }}>{phone || "—"}</span>
                </p>
                <DotPulse />
              </div>
            )}

            {(stage === "prompt" || stage === "typing-pin" || stage === "confirming") && (
              <div
                className="w-full rounded-md px-3 py-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap"
                style={{
                  background: "linear-gradient(180deg,#0f1f14,#081209)",
                  color: LIME,
                  border: `1px solid ${GREEN_DARK}`,
                  minHeight: "120px",
                }}
              >
                {typed}
                <span className="animate-pulse">▌</span>
                {stage === "typing-pin" && (
                  <div className="mt-2 flex gap-1.5 justify-center">
                    {[0, 1, 2, 3].map((i) => (
                      <span
                        key={i}
                        className="w-2 h-2 rounded-full"
                        style={{ background: LIME, animation: `pinDot 1.2s ${i * 0.15}s infinite` }}
                      />
                    ))}
                  </div>
                )}
                {stage === "confirming" && (
                  <p className="mt-2 text-white/60 text-[10px]">Confirming with Safaricom…</p>
                )}
              </div>
            )}

            {stage === "success" && (
              <div className="text-center animate-[popIn_0.4s_ease-out]">
                <CheckCircle2 size={40} color={GREEN} className="mx-auto mb-2" />
                <p className="text-white text-[12px] font-semibold font-mono">Payment Received</p>
                <p className="text-white/50 text-[10px] font-mono mt-1">{receipt || "—"}</p>
              </div>
            )}

            {stage === "failed" && (
              <div className="text-center animate-[popIn_0.4s_ease-out]">
                <XCircle size={40} color="#ff5252" className="mx-auto mb-2" />
                <p className="text-white text-[12px] font-semibold font-mono">Payment Failed</p>
                <p className="text-white/40 text-[10px] font-mono mt-1">Customer cancelled or timed out</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DotPulse() {
  return (
    <div className="flex gap-1 justify-center mt-2">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: GREEN, animation: `pinDot 1s ${i * 0.18}s infinite` }}
        />
      ))}
    </div>
  );
}

/* ------------------------------ Status Pill ----------------------------- */

function QrScreen({ loading, qrCode, amount, qrRef }) {
  return (
    <div className="relative w-[240px] sm:w-[260px] mx-auto select-none">
      <div
        className="rounded-2xl p-6 flex flex-col items-center"
        style={{
          background: "linear-gradient(160deg,#0f1f14,#081209)",
          border: `1px solid ${GREEN_DARK}`,
        }}
      >
        <div
          className="relative w-[180px] h-[180px] rounded-lg flex items-center justify-center overflow-hidden"
          style={{ background: "#ffffff" }}
        >
          {loading && (
            <Loader2 className="animate-spin" size={28} color={GREEN_DARK} />
          )}

          {!loading && !qrCode && (
            <div className="text-center px-3">
              <p className="text-[11px] text-black/30 font-mono">
                Enter an amount to generate a code
              </p>
            </div>
          )}

          {!loading && qrCode && (
            <>
              <img
                src={`data:image/png;base64,${qrCode}`}
                alt="M-Pesa QR code"
                className="w-full h-full object-contain animate-[popIn_0.4s_ease-out]"
              />
              {/* animated scan line */}
              <div
                className="absolute left-0 right-0 h-[3px]"
                style={{
                  background: `linear-gradient(90deg, transparent, ${GREEN}, transparent)`,
                  animation: "scanLine 2.2s ease-in-out infinite",
                }}
              />
            </>
          )}
        </div>

        <p className="mt-4 text-white text-[12px] font-mono">
          {amount ? `KSh ${amount}` : "—"}
        </p>
        {qrRef && (
          <p className="mt-1 text-white/40 text-[10px] font-mono">ref: {qrRef}</p>
        )}
        <p className="mt-3 text-white/30 text-[10px] text-center leading-relaxed">
          Customer opens M-Pesa → Scan QR
          <br />
          to pay this amount instantly.
        </p>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    SUCCESS: { bg: `${GREEN}1A`, fg: GREEN, label: "Success", icon: CheckCircle2 },
    Pending: { bg: "#FFB80022", fg: "#C98A00", label: "Pending", icon: Clock },
    FAILED: { bg: "#FF52521A", fg: "#E13B3B", label: "Failed", icon: XCircle },
  };
  const s = map[status] || map.Pending;
  const Icon = s.icon;
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium"
      style={{ background: s.bg, color: s.fg }}
    >
      <Icon size={12} />
      {s.label}
    </span>
  );
}

/* -------------------------------- App ----------------------------------- */

export default function PaymentDashboard() {
  const [mode, setMode] = useState("stk"); // "stk" | "qr"
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [stage, setStage] = useState("idle");
  const [error, setError] = useState("");
  const [activeReceipt, setActiveReceipt] = useState("");
  const [payments, setPayments] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const pollRef = useRef(null);

  // Scan-to-pay state
  const [qrAmount, setQrAmount] = useState("");
  const [qrCode, setQrCode] = useState(""); // base64 png string
  const [qrLoading, setQrLoading] = useState(false);
  const [qrError, setQrError] = useState("");
  const [qrRef, setQrRef] = useState("");

  const validPhone = /^2547\d{8}$|^2541\d{8}$/.test(phone);
  const validAmount = Number(amount) > 0;

  const fetchPayments = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await api.listPayments();
      setPayments(Array.isArray(data) ? data : []);
    } catch (e) {
      // Backend may not be running in this preview — fail quietly.
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPoll(), []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!validPhone) {
      setError("Enter a valid Safaricom number, e.g. 2547XXXXXXXX");
      return;
    }
    if (!validAmount) {
      setError("Enter an amount greater than 0");
      return;
    }

    setStage("dialing");

    try {
      const data = await api.pay({ phone, amount: Number(amount) });

      // Move into the on-screen USSD sequence
      setTimeout(() => setStage("prompt"), 600);
      setTimeout(() => setStage("typing-pin"), 2400);
      setTimeout(() => setStage("confirming"), 4200);

      const checkoutId = data.checkout_id;

      pollRef.current = setInterval(async () => {
        try {
          const list = await api.listPayments();
          const match = list.find((p) => p.checkout_request_id === checkoutId);
          if (match && match.status !== "Pending") {
            stopPoll();
            if (match.status === "SUCCESS") {
              setActiveReceipt(match.mpesa_receipt || "");
              setStage("success");
            } else {
              setStage("failed");
            }
            fetchPayments();
          }
        } catch {
          /* keep polling */
        }
      }, 2500);

      // Safety timeout: stop polling after 45s
      setTimeout(() => {
        stopPoll();
        setStage((s) => (s === "confirming" || s === "prompt" || s === "typing-pin" ? "failed" : s));
      }, 45000);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the payment service. Check your connection and try again."
      );
      setStage("idle");
    }
  };

  const resetFlow = () => {
    stopPoll();
    setStage("idle");
    setActiveReceipt("");
    setPhone("");
    setAmount("");
    fetchPayments();
  };

  const handleGenerateQr = async (e) => {
    e.preventDefault();
    setQrError("");
    if (!(Number(qrAmount) > 0)) {
      setQrError("Enter an amount greater than 0");
      return;
    }
    setQrLoading(true);
    setQrCode("");
    try {
      const data = await api.generateQr({ amount: Number(qrAmount) });
      setQrRef(data.account_ref || "");
      if (data.qr_code) {
        setQrCode(data.qr_code);
      } else {
        throw new Error("Server did not return a QR image");
      }
    } catch (err) {
      setQrError(err.message || "Something went wrong generating the QR code.");
    } finally {
      setQrLoading(false);
    }
  };

  const resetQr = () => {
    setQrCode("");
    setQrAmount("");
    setQrError("");
    setQrRef("");
  };

  const busy = ["dialing", "prompt", "typing-pin", "confirming"].includes(stage);

  return (
    <div
      className="min-h-screen w-full relative overflow-hidden font-sans"
      style={{
        background: "radial-gradient(1200px 600px at 80% -10%, #0d2e1a 0%, #06140c 45%, #050a07 100%)",
        color: "#EAF5EE",
      }}
    >
      <style>{`
        @keyframes pinDot { 0%,80%,100%{opacity:.25; transform:translateY(0)} 40%{opacity:1; transform:translateY(-3px)} }
        @keyframes popIn { 0%{opacity:0; transform:scale(.85)} 100%{opacity:1; transform:scale(1)} }
        @keyframes floatSlow { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @keyframes shimmer { 0%{background-position:-400px 0} 100%{background-position:400px 0} }
        @keyframes scanLine { 0%{top:6%} 50%{top:92%} 100%{top:6%} }
        .signal-ring { animation: floatSlow 6s ease-in-out infinite; }
        ::selection { background:#00A65133; }
      `}</style>

      {/* ambient ring decoration */}
      <div
        className="absolute -top-32 -right-32 w-[460px] h-[460px] rounded-full signal-ring"
        style={{ background: `radial-gradient(circle, ${GREEN}22 0%, transparent 70%)` }}
      />
      <div
        className="absolute top-40 -left-40 w-[380px] h-[380px] rounded-full signal-ring"
        style={{ background: `radial-gradient(circle, ${LIME}14 0%, transparent 70%)`, animationDelay: "1.5s" }}
      />

      {/* header */}
      <header className="relative z-10 max-w-6xl mx-auto px-6 pt-10 pb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-black"
            style={{ background: `linear-gradient(135deg, ${LIME}, ${GREEN})` }}
          >
            KP
          </div>
          <div>
            <p className="font-semibold tracking-tight leading-none">Kiarie Pay</p>
            <p className="text-[11px] text-white/40 leading-none mt-1">Lipa na M-Pesa, instantly</p>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-[11px] text-white/40 font-mono">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: GREEN }} />
          sandbox · daraja
        </div>
      </header>

      {/* hero / main grid */}
      <main className="relative z-10 max-w-6xl mx-auto px-6 grid lg:grid-cols-[1fr_340px] gap-10 pb-16">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-2">
            Request a payment in
            <span style={{ color: GREEN }}> one tap.</span>
          </h1>
          <p className="text-white/50 text-sm mb-6 max-w-md">
            Send an STK push straight to the customer's phone, or generate a QR
            code for them to scan — watch it happen live, on the screen beside this form.
          </p>

          {/* tab switcher */}
          <div
            className="inline-flex p-1 rounded-lg mb-6"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
          >
            {[
              { key: "stk", label: "STK Push" },
              { key: "qr", label: "Scan to Pay" },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setMode(t.key)}
                className="px-4 py-1.5 rounded-md text-[13px] font-medium transition-all"
                style={
                  mode === t.key
                    ? { background: `linear-gradient(135deg, ${LIME}, ${GREEN})`, color: "#06140c" }
                    : { color: "rgba(255,255,255,0.5)" }
                }
              >
                {t.label}
              </button>
            ))}
          </div>

          {mode === "stk" ? (
          <form
            onSubmit={handleSubmit}
            className="rounded-2xl p-6 sm:p-8 max-w-md"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
              backdropFilter: "blur(8px)",
            }}
          >
            <label className="block text-[12px] text-white/50 mb-1.5">Customer phone number</label>
            <input
              type="tel"
              placeholder="2547XXXXXXXX"
              value={phone}
              disabled={busy}
              onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, ""))}
              className="w-full mb-4 px-4 py-3 rounded-lg bg-black/30 border border-white/10 outline-none font-mono text-sm tracking-wide focus:ring-2 transition"
              style={{ "--tw-ring-color": GREEN }}
              onFocus={(e) => (e.target.style.borderColor = GREEN)}
              onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
            />

            <label className="block text-[12px] text-white/50 mb-1.5">Amount (KSh)</label>
            <input
              type="number"
              min="1"
              placeholder="0"
              value={amount}
              disabled={busy}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full mb-2 px-4 py-3 rounded-lg bg-black/30 border border-white/10 outline-none font-mono text-sm focus:ring-2 transition"
              onFocus={(e) => (e.target.style.borderColor = GREEN)}
              onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
            />

            {error && <p className="text-[12px] text-red-400 mt-2">{error}</p>}

            <button
              type="submit"
              disabled={busy}
              className={classNames(
                "w-full mt-5 py-3 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-transform active:scale-[0.98]",
                busy ? "opacity-60 cursor-not-allowed" : "hover:brightness-110"
              )}
              style={{ background: `linear-gradient(135deg, ${LIME}, ${GREEN})`, color: "#06140c" }}
            >
              {busy ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Sending push…
                </>
              ) : (
                <>
                  Send STK push <ArrowRight size={16} />
                </>
              )}
            </button>

            {(stage === "success" || stage === "failed") && (
              <button
                type="button"
                onClick={resetFlow}
                className="w-full mt-3 py-2.5 rounded-lg text-sm font-medium border border-white/15 text-white/70 hover:text-white hover:border-white/30 transition"
              >
                New payment request
              </button>
            )}
          </form>
          ) : (
          <form
            onSubmit={handleGenerateQr}
            className="rounded-2xl p-6 sm:p-8 max-w-md"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
              backdropFilter: "blur(8px)",
            }}
          >
            <label className="block text-[12px] text-white/50 mb-1.5">Amount (KSh)</label>
            <input
              type="number"
              min="1"
              placeholder="0"
              value={qrAmount}
              disabled={qrLoading}
              onChange={(e) => setQrAmount(e.target.value)}
              className="w-full mb-2 px-4 py-3 rounded-lg bg-black/30 border border-white/10 outline-none font-mono text-sm focus:ring-2 transition"
              onFocus={(e) => (e.target.style.borderColor = GREEN)}
              onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
            />

            {qrError && <p className="text-[12px] text-red-400 mt-2">{qrError}</p>}

            <button
              type="submit"
              disabled={qrLoading}
              className={classNames(
                "w-full mt-5 py-3 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-transform active:scale-[0.98]",
                qrLoading ? "opacity-60 cursor-not-allowed" : "hover:brightness-110"
              )}
              style={{ background: `linear-gradient(135deg, ${LIME}, ${GREEN})`, color: "#06140c" }}
            >
              {qrLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Generating code…
                </>
              ) : (
                <>
                  Generate QR code <ArrowRight size={16} />
                </>
              )}
            </button>

            {qrCode && (
              <button
                type="button"
                onClick={resetQr}
                className="w-full mt-3 py-2.5 rounded-lg text-sm font-medium border border-white/15 text-white/70 hover:text-white hover:border-white/30 transition"
              >
                New QR code
              </button>
            )}
          </form>
          )}

          {/* recent payments */}
          {mode === "stk" && (
          <div className="mt-10">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white/70 flex items-center gap-2">
                <Receipt size={15} /> Recent transactions
              </h2>
              {loadingList && <Loader2 size={14} className="animate-spin text-white/30" />}
            </div>

            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid rgba(255,255,255,0.08)" }}
            >
              {payments.length === 0 ? (
                <div className="px-5 py-8 text-center text-white/30 text-sm">
                  No transactions yet — they'll appear here once a payment is sent.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] text-white/40 bg-white/[0.03]">
                      <th className="px-4 py-2.5 font-medium">Phone</th>
                      <th className="px-4 py-2.5 font-medium">Amount</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Receipt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.slice(0, 8).map((p) => (
                      <tr key={p.id} className="border-t border-white/5 hover:bg-white/[0.02] transition">
                        <td className="px-4 py-2.5 font-mono text-[12.5px]">{p.phone}</td>
                        <td className="px-4 py-2.5 font-mono text-[12.5px]">KSh {p.amount}</td>
                        <td className="px-4 py-2.5">
                          <StatusPill status={p.status} />
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[12px] text-white/50">
                          {p.mpesa_receipt || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
          )}
        </div>

        {/* phone / qr preview column */}
        <div className="flex flex-col items-center justify-start pt-2">
          <p className="text-[11px] uppercase tracking-wider text-white/30 mb-4 text-center">
            {mode === "stk" ? "Live customer screen" : "Customer scans this"}
          </p>
          {mode === "stk" ? (
            <PhoneScreen stage={stage} phone={phone} amount={amount} receipt={activeReceipt} />
          ) : (
            <QrScreen loading={qrLoading} qrCode={qrCode} amount={qrAmount} qrRef={qrRef} />
          )}
        </div>
      </main>
    </div>
  );
}