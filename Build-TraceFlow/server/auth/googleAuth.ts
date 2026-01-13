import passport from "passport";
import { Strategy as GoogleStrategy } from "passport-google-oauth20";
import session from "express-session";
import type { Express, RequestHandler } from "express";
import connectPg from "connect-pg-simple";
import { authStorage } from "../replit_integrations/auth/storage";

// Google OAuth Configuration
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const SESSION_SECRET = process.env.SESSION_SECRET;
const CALLBACK_URL = process.env.GOOGLE_CALLBACK_URL || "/api/auth/google/callback";

if (!GOOGLE_CLIENT_ID || !GOOGLE_CLIENT_SECRET) {
  console.warn("⚠️  Google OAuth credentials not configured. Authentication will not work.");
  console.warn("   Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.");
}

if (!SESSION_SECRET) {
  console.warn("⚠️  SESSION_SECRET not configured. Using fallback (NOT SECURE FOR PRODUCTION).");
}

export function getSession() {
  const sessionTtl = 7 * 24 * 60 * 60 * 1000; // 1 week

  // Only use PostgreSQL session store if DATABASE_URL is available
  let sessionStore;
  if (process.env.DATABASE_URL) {
    try {
      const pgStore = connectPg(session);
      sessionStore = new pgStore({
        conString: process.env.DATABASE_URL,
        createTableIfMissing: false,
        ttl: sessionTtl,
        tableName: "sessions",
      });
      console.log("✅ Using PostgreSQL session store");
    } catch (error) {
      console.warn("⚠️  Failed to initialize PostgreSQL session store, using memory store:", error);
      sessionStore = undefined;
    }
  } else {
    console.warn("⚠️  DATABASE_URL not set, using in-memory session store (sessions will not persist across restarts)");
  }

  return session({
    secret: SESSION_SECRET || "fallback-secret-change-in-production",
    store: sessionStore,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: sessionTtl,
      sameSite: process.env.NODE_ENV === "production" ? "lax" : "none",
    },
  });
}

export async function setupGoogleAuth(app: Express) {
  // Trust proxy for Cloud Run
  app.set("trust proxy", 1);

  // Setup session
  app.use(getSession());
  app.use(passport.initialize());
  app.use(passport.session());

  // Configure Google OAuth Strategy
  if (GOOGLE_CLIENT_ID && GOOGLE_CLIENT_SECRET) {
    passport.use(
      new GoogleStrategy(
        {
          clientID: GOOGLE_CLIENT_ID,
          clientSecret: GOOGLE_CLIENT_SECRET,
          callbackURL: CALLBACK_URL,
          scope: ["profile", "email"],
        },
        async (accessToken, refreshToken, profile, done) => {
          try {
            // Extract user info from Google profile
            const email = profile.emails?.[0]?.value;
            const firstName = profile.name?.givenName;
            const lastName = profile.name?.familyName;
            const profileImageUrl = profile.photos?.[0]?.value;

            if (!email) {
              return done(new Error("No email found in Google profile"));
            }

            // Upsert user in database
            await authStorage.upsertUser({
              id: profile.id,
              email,
              firstName,
              lastName,
              profileImageUrl,
              googleId: profile.id,
            });

            // Create user session object
            const user = {
              id: profile.id,
              email,
              firstName,
              lastName,
              profileImageUrl,
              googleId: profile.id,
            };

            done(null, user);
          } catch (error) {
            console.error("Error in Google OAuth callback:", error);
            done(error as Error);
          }
        }
      )
    );
  }

  // Serialize/deserialize user for session
  passport.serializeUser((user: any, done) => {
    done(null, user);
  });

  passport.deserializeUser((user: any, done) => {
    done(null, user);
  });

  // Auth routes
  app.get("/api/auth/google", (req, res, next) => {
    if (!GOOGLE_CLIENT_ID) {
      return res.status(500).json({
        error: "Google OAuth not configured",
        message: "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables"
      });
    }
    passport.authenticate("google", {
      scope: ["profile", "email"],
    })(req, res, next);
  });

  app.get("/api/auth/google/callback",
    passport.authenticate("google", {
      failureRedirect: "/auth?error=google_auth_failed",
    }),
    (req, res) => {
      // Successful authentication
      res.redirect("/");
    }
  );

  // Get current user
  app.get("/api/auth/me", isAuthenticated, (req: any, res) => {
    res.json(req.user);
  });

  // Logout
  app.get("/api/auth/logout", (req, res) => {
    req.logout((err) => {
      if (err) {
        console.error("Logout error:", err);
      }
      res.redirect("/");
    });
  });

  // Health check for auth
  app.get("/api/auth/status", (req, res) => {
    res.json({
      configured: !!(GOOGLE_CLIENT_ID && GOOGLE_CLIENT_SECRET),
      authenticated: req.isAuthenticated(),
      session: !!req.session,
    });
  });
}

export const isAuthenticated: RequestHandler = (req, res, next) => {
  if (req.isAuthenticated()) {
    return next();
  }
  res.status(401).json({
    message: "Not authenticated",
    loginUrl: "/api/auth/google"
  });
};
