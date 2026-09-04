import { useNavigate } from "react-router-dom";
import ErrorState from "../components/ui/ErrorState";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-6">
      <div className="w-full max-w-md">
        <ErrorState
          title="Page not found"
          description="The page you're looking for doesn't exist or has moved."
          onRetry={() => navigate("/")}
          retryLabel="Back to Landing"
        />
      </div>
    </div>
  );
}
