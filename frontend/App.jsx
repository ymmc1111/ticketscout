import React, { useState, useEffect } from 'react';
import { initializeApp } from "firebase/app";
import { getFirestore, collection, addDoc, deleteDoc, doc, query, onSnapshot, orderBy, serverTimestamp } from "firebase/firestore";
import { getAuth, signInWithCustomToken, signInAnonymously } from "firebase/auth";

// Initialize Firebase
const firebaseConfig = window.__firebase_config || {};
const isConfigured = firebaseConfig.projectId && firebaseConfig.projectId !== "YOUR_PROJECT_ID";

let app, db, auth;

// Mock Data Store for Local Preview
const mockDb = {
    jobs: [
        {
            id: 'mock-1',
            eventID: 'JIMMY-HENDRIX-EXP',
            contact: 'jimmy.hendrix@mail.com', // UPDATED TO EMAIL
            status: 'ACTIVE',
            mode: 'DEMO',
            createdAt: new Date(),
            current_availability: JSON.stringify({ status: 'FEW_TICKETS_LEFT', last_checked: new Date().toISOString(), priceMin: 350, priceMax: 1200 })
        }
    ],
    listeners: [],
    addJob: (job) => {
        mockDb.jobs = [job, ...mockDb.jobs];
        mockDb.notify();
    },
    deleteJob: (id) => {
        mockDb.jobs = mockDb.jobs.filter(job => job.id !== id);
        mockDb.notify();
    },
    notify: () => {
        mockDb.listeners.forEach(cb => cb([...mockDb.jobs]));
    },
    subscribe: (cb) => {
        mockDb.listeners.push(cb);
        cb([...mockDb.jobs]);
        return () => {
            mockDb.listeners = mockDb.listeners.filter(l => l !== cb);
        };
    }
};

if (isConfigured) {
    app = initializeApp(firebaseConfig);
    db = getFirestore(app);
    auth = getAuth(app);

    if (window.__initial_auth_token) {
        signInWithCustomToken(auth, window.__initial_auth_token)
            .then(() => console.log("Authenticated"))
            .catch((err) => console.error("Auth failed", err));
    }
} else {
    console.warn("⚠️ Firebase not configured. Running in LOCAL PREVIEW MODE.");
    // Mock Auth
    auth = {
        currentUser: { uid: "local-dev-user", isAnonymous: true },
        onAuthStateChanged: (cb) => {
            setTimeout(() => cb({ uid: "local-dev-user", isAnonymous: true }), 500);
            return () => { };
        }
    };
}



// --- COMPONENTS ---
const ConfirmationModal = ({ isOpen, onClose, onConfirm, title, message }) => {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose}></div>
            <div className="relative bg-white border-2 border-black p-6 w-full max-w-md shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
                <div className="bg-red-500 text-white text-[10px] font-bold uppercase tracking-widest px-2 py-1 inline-block mb-4">
                    Warning: Irreversible Action
                </div>
                <h3 className="text-xl font-bold uppercase mb-2">{title}</h3>
                <p className="font-mono text-xs text-gray-600 mb-6 leading-relaxed">
                    {message}
                </p>
                <div className="flex gap-4">
                    <button
                        onClick={onClose}
                        className="flex-1 h-12 border-2 border-black font-bold uppercase hover:bg-gray-100 transition-colors text-xs"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex-1 h-12 bg-red-500 text-white font-bold uppercase hover:bg-red-600 transition-colors text-xs"
                    >
                        Confirm Archive
                    </button>
                </div>
            </div>
        </div>
    );
};

const App = () => {
    const [jobs, setJobs] = useState([]);
    const [eventId, setEventId] = useState("");
    const [contact, setContact] = useState("");
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(null);
    const [isDemoMode, setIsDemoMode] = useState(true); // Default to Demo

    // Modal State
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [jobToDelete, setJobToDelete] = useState(null);

    useEffect(() => {
        const unsubscribe = auth.onAuthStateChanged((u) => {
            console.log("Auth State Changed:", u);
            if (u) {
                setUser(u);
            } else {
                console.log("No user signed in. Attempting Anonymous Auth...");
                signInAnonymously(auth).catch((error) => {
                    console.error("Anonymous Auth Failed:", error);
                    alert("Auth Failed: Enable Anonymous Auth in Firebase Console!");
                });
            }
        });
        return unsubscribe;
    }, []);

    useEffect(() => {
        if (!user || !window.__app_id) return;

        if (isConfigured) {
            // Requirement: /artifacts/{appId}/users/{userId}/ticket_monitors
            const path = `artifacts/${window.__app_id}/users/${user.uid}/ticket_monitors`;
            const q = query(collection(db, path), orderBy("createdAt", "desc"));

            const unsubscribe = onSnapshot(q, (snapshot) => {
                const jobsData = snapshot.docs.map(doc => ({
                    id: doc.id,
                    ...doc.data()
                }));
                setJobs(jobsData);
            });
            return unsubscribe;
        } else {
            // Mock Subscription
            return mockDb.subscribe(setJobs);
        }
    }, [user]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!user || !eventId || !contact) return;

        setLoading(true);
        console.log("Submitting job...", { eventId, contact, user });
        try {
            const jobData = {
                eventID: eventId,
                contact: contact,
                targetStatus: "TICKETS_AVAILABLE",
                current_availability: JSON.stringify({ status: "UNKNOWN", last_checked: null }),
                status: "ACTIVE",
                mode: isDemoMode ? 'DEMO' : 'LIVE',
                createdAt: isConfigured ? serverTimestamp() : new Date()
            };

            if (isConfigured) {
                console.log("Saving to Firestore...", jobData);
                const path = `artifacts/${window.__app_id}/users/${user.uid}/ticket_monitors`;
                const docRef = await addDoc(collection(db, path), jobData);
                console.log("Document written with ID: ", docRef.id);
            } else {
                // Mock Add
                console.log("Saving to Mock DB...", jobData);
                await new Promise(r => setTimeout(r, 800)); // Fake network delay
                mockDb.addJob({ ...jobData, id: `local-${Date.now()}` });
            }

            setEventId("");
            setContact("");
        } catch (err) {
            console.error("Error adding job:", err);
            alert("Error adding job: " + err.message); // Add visible alert
        }
        setLoading(false);
    };

    const handleDelete = (jobId) => {
        setJobToDelete(jobId);
        setShowDeleteModal(true);
    };

    const confirmDelete = async () => {
        if (!jobToDelete) return;

        if (isConfigured) {
            const path = `artifacts/${window.__app_id}/users/${user.uid}/ticket_monitors`;
            await deleteDoc(doc(db, path, jobToDelete));
        } else {
            mockDb.deleteJob(jobToDelete);
        }

        setShowDeleteModal(false);
        setJobToDelete(null);
    };

    // --- DESIGN SYSTEM CONSTANTS ---
    const ACCENT_COLOR = "bg-[#FF4500]"; // Electric Orange
    const ACCENT_TEXT = "text-[#FF4500]";
    const ACCENT_BORDER = "border-[#FF4500]";

    // Helper for conditional classes
    const cn = (...classes) => classes.filter(Boolean).join(' ');

    return (
        <div className="min-h-screen bg-[#F4F4F4] text-black selection:bg-[#FF4500] selection:text-white flex flex-col">

            {/* TOP BAR: FIXED & TECHNICAL */}
            <header className="sticky top-0 z-50 bg-white border-b-2 border-black flex justify-between items-stretch h-16">
                <div className="flex items-center px-6 border-r-2 border-black bg-black text-white">
                    <div className="w-3 h-3 bg-[#FF4500] mr-3 animate-pulse"></div>
                    <h1 className="text-xl font-bold tracking-tight uppercase">Ticket Scout <span className="font-mono text-xs opacity-50 ml-1">v1.0</span></h1>
                </div>

                <div className="flex-1 flex items-center px-4 font-mono text-[10px] uppercase tracking-widest text-gray-500 hidden md:flex">
                    System Status: {isConfigured ? "ONLINE" : "OFFLINE PREVIEW"} // Latency: &lt;12ms
                </div>

                <div className="flex">
                    {/* MODE TOGGLE - MECHANICAL SWITCH STYLE */}
                    <div className="flex border-l-2 border-black">
                        <button
                            onClick={() => setIsDemoMode(true)}
                            className={cn(
                                "px-6 flex items-center justify-center text-xs font-bold uppercase transition-all",
                                isDemoMode ? "bg-[#FF4500] text-white" : "bg-white hover:bg-gray-100"
                            )}
                        >
                            Demo
                        </button>
                        <div className="w-[2px] bg-black"></div>
                        <button
                            onClick={() => setIsDemoMode(false)}
                            className={cn(
                                "px-6 flex items-center justify-center text-xs font-bold uppercase transition-all",
                                !isDemoMode ? "bg-black text-white" : "bg-white hover:bg-gray-100"
                            )}
                        >
                            Live
                        </button>
                    </div>
                </div>
            </header>

            <main className="flex-1 p-4 md:p-8 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-8">

                {/* LEFT COLUMN: CONTROLS (4 Cols) */}
                <div className="lg:col-span-4 flex flex-col gap-8">

                    {/* INPUT MODULE */}
                    <section className="border-2 border-black bg-white">
                        <div className="bg-black text-white px-3 py-1 text-[10px] font-bold uppercase tracking-widest flex justify-between">
                            <span>Input_Module.01</span>
                            <span>{isDemoMode ? "TESTING" : "ACTIVE"}</span>
                        </div>

                        <form onSubmit={handleSubmit} className="p-0">
                            <div className="border-b-2 border-black p-4 group focus-within:bg-[#FF4500]/5 transition-colors">
                                <label className="block text-[10px] font-bold uppercase mb-2 text-gray-500 group-focus-within:text-[#FF4500]">Target Event ID</label>
                                <input
                                    type="text"
                                    value={eventId}
                                    onChange={(e) => setEventId(e.target.value)}
                                    placeholder="ENTER_ID..."
                                    className="w-full bg-transparent text-xl font-bold uppercase outline-none placeholder-gray-300 font-mono"
                                    required
                                />
                            </div>

                            <div className="border-b-2 border-black p-4 group focus-within:bg-[#FF4500]/5 transition-colors">
                                <label className="block text-[10px] font-bold uppercase mb-2 text-gray-500 group-focus-within:text-[#FF4500]">Contact (Email Address)</label> {/* UPDATED LABEL */}
                                <input
                                    type="email" // Changed type for better mobile/browser experience
                                    value={contact}
                                    onChange={(e) => setContact(e.target.value)}
                                    placeholder="ENTER_EMAIL..." // UPDATED PLACEHOLDER
                                    className="w-full bg-transparent text-xl font-bold uppercase outline-none placeholder-gray-300 font-mono"
                                    required
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading || !user}
                                className="w-full h-16 bg-white hover:bg-black hover:text-white disabled:opacity-50 disabled:hover:bg-white disabled:hover:text-black transition-colors text-lg font-bold uppercase flex items-center justify-between px-6 group"
                            >
                                <span>{loading ? "Processing..." : "Initiate Sequence"}</span>
                                <span className="group-hover:translate-x-1 transition-transform">→</span>
                            </button>
                        </form>
                    </section>

                    {/* SYSTEM INFO */}
                    <section className="border-2 border-black bg-white p-4 font-mono text-xs">
                        <div className="mb-4 text-[10px] font-bold uppercase tracking-widest text-gray-400 border-b border-black pb-1">System_Diagnostics</div>
                        <div className="grid grid-cols-2 gap-y-2">
                            <div className="text-gray-500">USER_ID:</div>
                            <div className="text-right truncate">{user ? user.uid.substring(0, 8) + '...' : 'N/A'}</div>

                            <div className="text-gray-500">DB_CONNECTION:</div>
                            <div className="text-right">{isConfigured ? "FIREBASE_V9" : "LOCAL_MOCK"}</div>

                            <div className="text-gray-500">ACTIVE_JOBS:</div>
                            <div className="text-right">{jobs.length}</div>
                        </div>

                        {!user && (
                            <div className="mt-4 p-2 bg-[#FF4500] text-white text-center font-bold uppercase">
                                ! AUTH REQUIRED
                            </div>
                        )}
                    </section>
                </div>

                {/* RIGHT COLUMN: MONITOR GRID (8 Cols) */}
                <div className="lg:col-span-8">
                    <div className="flex justify-between items-end mb-4 border-b-2 border-black pb-2">
                        <h2 className="text-2xl font-bold uppercase tracking-tight">Active Monitors</h2>
                        <div className="font-mono text-[10px] uppercase">Auto-Refresh: <span className="bg-black text-white px-1">ON</span></div>
                    </div>

                    <div className="grid grid-cols-1 gap-4">
                        {jobs.length === 0 && (
                            <div className="border-2 border-black border-dashed h-64 flex flex-col items-center justify-center text-gray-300">
                                <div className="text-4xl mb-2">∅</div>
                                <div className="font-mono text-sm uppercase">No Active Sequences</div>
                            </div>
                        )}

                        {jobs.map((job) => {
                            let availability = {};
                            try {
                                availability = typeof job.current_availability === 'string'
                                    ? JSON.parse(job.current_availability)
                                    : job.current_availability;
                            } catch (e) { availability = {}; }

                            const isAvailable = availability.status === "TICKETS_AVAILABLE";
                            const isFew = availability.status === "FEW_TICKETS_LEFT";

                            return (
                                <div key={job.id} className="border-2 border-black bg-white flex flex-col md:flex-row h-auto md:h-32 transition-transform hover:-translate-y-1 hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">

                                    {/* STATUS STRIP */}
                                    <div className={cn(
                                        "w-full md:w-2 flex-shrink-0 border-b-2 md:border-b-0 md:border-r-2 border-black",
                                        isAvailable ? "bg-[#FF4500]" : (isFew ? "bg-yellow-400" : "bg-gray-200")
                                    )}></div>

                                    {/* DATA BLOCK */}
                                    <div className="flex-1 p-4 flex flex-col justify-between">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Event_Target</div>
                                                <div className="text-xl font-bold uppercase tracking-tight">{job.eventID}</div>
                                            </div>
                                            <div className="flex items-center">
                                                <div className="font-mono text-[10px] border border-black px-1 pt-[2px] uppercase">
                                                    {job.mode}
                                                </div>
                                                <button
                                                    onClick={() => handleDelete(job.id)}
                                                    className="font-mono text-[10px] border border-red-500 text-red-500 hover:bg-red-500 hover:text-white px-2 pt-[2px] uppercase transition-colors ml-2"
                                                >
                                                    Archive
                                                </button>
                                            </div>
                                        </div>

                                        <div className="flex gap-8 mt-2">
                                            <div>
                                                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Contact (Email)</div>
                                                <div className="font-mono text-sm">{job.contact}</div>
                                            </div>
                                            <div>
                                                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Created</div>
                                                <div className="font-mono text-sm">
                                                    {job.createdAt?.seconds ? new Date(job.createdAt.seconds * 1000).toLocaleDateString() : 'Just now'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* LIVE METRICS BLOCK */}
                                    <div className="w-full md:w-64 border-t-2 md:border-t-0 md:border-l-2 border-black bg-[#F9F9F9] p-4 flex flex-col justify-center relative overflow-hidden">
                                        {/* Background Grid Pattern */}
                                        <div className="absolute inset-0 opacity-5 pointer-events-none"
                                            style={{ backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)', backgroundSize: '10px 10px' }}>
                                        </div>

                                        <div className="relative z-10">
                                            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Current Status</div>
                                            <div className={cn(
                                                "text-sm font-bold uppercase inline-block border border-black px-2 py-1 mb-2",
                                                job.status === 'ACTIVE' ? "bg-green-500 text-white" : "bg-red-500 text-white"
                                            )}>
                                                {job.status === 'ACTIVE' ? "RUNNING" : "RUN"}
                                            </div>

                                            <div className="flex justify-between items-end border-t border-gray-300 pt-2">
                                                <span className="text-[10px] font-bold uppercase text-gray-400">Last Check</span>
                                                <span className="font-mono text-xs">
                                                    {availability.last_checked ? new Date(availability.last_checked).toLocaleTimeString([], { hour12: false }) : "--:--:--"}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </main >

            {/* FOOTER */}
            <footer className="border-t-2 border-black bg-white p-4 text-[10px] font-bold uppercase tracking-widest flex justify-between items-center">
                <div>
                    <span className="bg-black text-white px-1 mr-2">TE-STYLE</span>
                    Ticket Scout Systems © 2025
                </div>
                <div className="hidden md:block text-gray-400">
                    Designed for High-Performance Monitoring
                </div>
            </footer>

            <ConfirmationModal
                isOpen={showDeleteModal}
                onClose={() => setShowDeleteModal(false)}
                onConfirm={confirmDelete}
                title="Archive Monitor?"
                message="Are you sure you want to archive this monitor? This will stop all tracking and notifications for this event. This action cannot be undone."
            />
        </div >
    );
};

export default App;