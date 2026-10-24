import { useRef, useState } from "react";

const CameraIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#c8460c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 8h3l2-2h6l2 2h3v11H4z" /><circle cx="12" cy="13" r="3.5" />
  </svg>
);
export const UserIcon = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#c8460c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
  </svg>
);

export default function PhotoPicker({ onChange, hint = "Optional. JPG or PNG, up to 2 MB." }) {
  const input = useRef(null);
  const [preview, setPreview] = useState(null);

  function pick(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 2 * 1024 * 1024) {
      alert("Choose an image under 2 MB");
      return;
    }
    setPreview(URL.createObjectURL(file));
    onChange?.(file);
  }

  return (
    <div className="ob-photo">
      <button type="button" className="ob-photo-btn" aria-label="Choose profile photo" onClick={() => input.current.click()}>
        {preview ? <img src={preview} alt="Your profile preview" /> : <CameraIcon />}
      </button>
      <input ref={input} type="file" accept="image/*" hidden onChange={pick} />
      <div className="ob-photo-text"><strong>Profile photo</strong>{hint}</div>
    </div>
  );
}