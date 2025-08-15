import React, { useEffect, useMemo, useState } from 'react';
import './index.css';

const API_BASE = (process && process.env && process.env.REACT_APP_BACKEND_URL) || '';

async function api(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* ignore */ }
  if (!res.ok) {
    const msg = (data && (data.detail || data.error || data.message)) || 'Request failed';
    throw new Error(msg);
  }
  return data;
}

function Section({ title, children }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xl font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('borrow');

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">BiblioFlow Web</h1>
          <nav className="flex gap-2">
            {['borrow','return','books','students','borrows'].map(t => (
              <button key={t} className={`btn ${tab===t? 'opacity-100':'opacity-80'}`} onClick={() => setTab(t)}>{t}</button>
            ))}
          </nav>
        </header>

        {tab === 'borrow' && <BorrowTab />}
        {tab === 'return' && <ReturnTab />}
        {tab === 'books' && <BooksTab />}
        {tab === 'students' && <StudentsTab />}
        {tab === 'borrows' && <BorrowsTab />}
      </div>
    </div>
  );
}

function BorrowTab() {
  const [studentQ, setStudentQ] = useState('');
  const [bookQ, setBookQ] = useState('');
  const [students, setStudents] = useState([]);
  const [books, setBooks] = useState([]);
  const [chosenStudent, setChosenStudent] = useState(null);
  const [chosenBook, setChosenBook] = useState(null);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        const s = await api(`/suggest/students?q=${encodeURIComponent(studentQ)}`);
        setStudents(s || []);
      } catch (e) {
        setStudents([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [studentQ]);

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        const b = await api(`/suggest/books?q=${encodeURIComponent(bookQ)}`);
        setBooks(b || []);
      } catch (e) {
        setBooks([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [bookQ]);

  const borrow = async () => {
    if (!chosenStudent || !chosenBook) return;
    setStatus('Processing...');
    try {
      await api('/borrow', { method: 'POST', body: JSON.stringify({ student_id: chosenStudent.id, book_code: chosenBook.sbin || chosenBook.stamp }) });
      setStatus('Borrowed successfully');
      setChosenBook(null); setBookQ('');
    } catch (e) {
      setStatus(e.message);
    }
  };

  return (
    <Section title="Borrow Book">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block mb-1">Student</label>
          <input className="input w-full" placeholder="Search name or admission number" value={studentQ} onChange={e => setStudentQ(e.target.value)} />
          <div className="mt-2 space-y-1 max-h-48 overflow-auto">
            {students.map(s => (
              <div key={s.id} className={`p-2 rounded cursor-pointer ${chosenStudent?.id===s.id? 'bg-blueGray/10':'hover:bg-blueGray/5'}`} onClick={() => setChosenStudent(s)}>
                {s.name} • {s.admission_number} {s.warnings? `(warnings: ${s.warnings})`: ''}
              </div>
            ))}
          </div>
        </div>
        <div>
          <label className="block mb-1">Book</label>
          <input className="input w-full" placeholder="Search title or code" value={bookQ} onChange={e => setBookQ(e.target.value)} />
          <div className="mt-2 space-y-1 max-h-48 overflow-auto">
            {books.map(b => (
              <div key={b.id} className={`p-2 rounded cursor-pointer ${chosenBook?.id===b.id? 'bg-blueGray/10':'hover:bg-blueGray/5'}`} onClick={() => setChosenBook(b)}>
                {b.title} {b.author? `• ${b.author}`:''} {b.sbin||b.stamp? `• ${b.sbin||b.stamp}`:''} {b.available? '':'• (not available)'}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2">
        <button className="btn" onClick={borrow}>Borrow</button>
        <span>{status}</span>
      </div>
    </Section>
  );
}

function ReturnTab() {
  const [code, setCode] = useState('');
  const [status, setStatus] = useState('');

  const submit = async () => {
    setStatus('Processing...');
    try {
      await api('/return', { method: 'POST', body: JSON.stringify({ book_code: code }) });
      setStatus('Returned successfully');
      setCode('');
    } catch (e) {
      setStatus(e.message);
    }
  };

  return (
    <Section title="Return Book">
      <div className="flex gap-2">
        <input className="input w-full" placeholder="Enter SBIN or Stamp code" value={code} onChange={e => setCode(e.target.value)} />
        <button className="btn" onClick={submit}>Return</button>
      </div>
      <div className="mt-2 text-sm">{status}</div>
    </Section>
  );
}

function BooksTab() {
  const [q, setQ] = useState('');
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ title: '', author: '', sbin: '', stamp: '' });
  const [status, setStatus] = useState('');

  const load = async () => {
    try {
      const result = await api(`/books?q=${encodeURIComponent(q)}`);
      setItems(result || []);
    } catch (e) {
      setItems([]);
      setStatus(e.message);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const create = async () => {
    try {
      await api('/books', { method: 'POST', body: JSON.stringify(form) });
      setForm({ title: '', author: '', sbin: '', stamp: '' });
      await load();
      setStatus('Created');
    } catch (e) { setStatus(e.message); }
  };

  const remove = async (id) => { try { await api(`/books/${id}`, { method: 'DELETE' }); await load(); } catch (e) { setStatus(e.message); } };

  return (
    <Section title="Manage Books">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div className="flex gap-2 mb-2">
            <input className="input w/full" placeholder="Search books" value={q} onChange={e => setQ(e.target.value)} />
            <button className="btn" onClick={load}>Search</button>
          </div>
          <div className="space-y-2 max-h-80 overflow-auto">
            {items.map(b => (
              <div key={b.id} className="p-2 border rounded flex items-center justify-between">
                <div>
                  <div className="font-medium">{b.title}</div>
                  <div className="text-sm opacity-80">{b.author} • {b.sbin || b.stamp} • {b.available? 'Available':'Borrowed'}</div>
                </div>
                <button className="btn" onClick={() => remove(b.id)}>Delete</button>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="space-y-2">
            <input className="input w-full" placeholder="Title" value={form.title} onChange={e => setForm(v => ({...v, title: e.target.value}))} />
            <input className="input w/full" placeholder="Author" value={form.author} onChange={e => setForm(v => ({...v, author: e.target.value}))} />
            <div className="grid grid-cols-2 gap-2">
              <input className="input w/full" placeholder="SBIN" value={form.sbin} onChange={e => setForm(v => ({...v, sbin: e.target.value}))} />
              <input className="input w/full" placeholder="Stamp" value={form.stamp} onChange={e => setForm(v => ({...v, stamp: e.target.value}))} />
            </div>
            <button className="btn" onClick={create}>Add Book</button>
            <div className="text-sm">{status}</div>
          </div>
        </div>
      </div>
    </Section>
  );
}

function StudentsTab() {
  const [q, setQ] = useState('');
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: '', admission_number: '', class_name: '' }); const [errors, setErrors] = useState({});
  const [status, setStatus] = useState('');

  const load = async () => setItems(await api(`/students?q=${encodeURIComponent(q)}`));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const create = async () => {
    // Frontend validation: admission_number exactly 6 chars
    const errs = {};
    if (!form.admission_number || form.admission_number.length !== 6) {
      errs.admission_number = 'Admission number must be exactly 6 characters';
    }
    if (!form.name) {
      errs.name = 'Name is required';
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    try {
      await api('/students', { method: 'POST', body: JSON.stringify(form) });
      setForm({ name: '', admission_number: '', class_name: '' });
      await load();
      setStatus('Created');
    } catch (e) { setStatus(e.message); }
  };

  const remove = async (id) => { try { await api(`/students/${id}`, { method: 'DELETE' }); await load(); } catch (e) { setStatus(e.message); } };

  return (
    <Section title="Manage Students">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div className="flex gap-2 mb-2">
            <input className="input w/full" placeholder="Search students" value={q} onChange={e => setQ(e.target.value)} />
            <button className="btn" onClick={load}>Search</button>
          </div>
          <div className="space-y-2 max-h-80 overflow-auto">
            {items.map(s => (
              <div key={s.id} className="p-2 border rounded flex items-center justify-between">
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-sm opacity-80">{s.admission_number} • {s.class_name || ''} • warnings: {s.warnings || 0}</div>
                </div>
                <button className="btn" onClick={() => remove(s.id)}>Delete</button>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="space-y-2">
            <input className="input w/full" placeholder="Name" value={form.name} onChange={e => setForm(v => ({...v, name: e.target.value}))} />
            {errors.name && <div className="text-sm text-red-600">{errors.name}</div>}
            <input className="input w/full" placeholder="Admission Number (6 chars)" value={form.admission_number} onChange={e => setForm(v => ({...v, admission_number: e.target.value}))} />
            {errors.admission_number && <div className="text-sm text-red-600">{errors.admission_number}</div>}
            <input className="input w/full" placeholder="Class" value={form.class_name} onChange={e => setForm(v => ({...v, class_name: e.target.value}))} />
            <button className="btn" onClick={create}>Add Student</button>
            <div className="text-sm">{status}</div>
          </div>
        </div>
      </div>
    </Section>
  );
}

function BorrowsTab() {
  const [items, setItems] = useState([]);
  const load = async () => setItems(await api('/borrows?active=true'));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  return (
    <Section title="Active Borrows">
      <div className="space-y-2">
        {items.map(b => (
          <div key={b.id} className="p-2 border rounded flex items-center justify-between">
            <div className="text-sm">
              <div>Borrow ID: {b.id}</div>
              <div>Borrowed: {new Date(b.borrow_date).toLocaleString()} • Due: {b.due_date ? new Date(b.due_date).toLocaleDateString(): '-'}</div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}