import { useRouter } from 'expo-router';
import { JobForm } from '@/components/job-form';
import { ScreenState } from '@/components/screen';
import { useAuth } from '@/lib/auth-context';
export default function NewJobScreen() {
  const router = useRouter(),
    auth = useAuth();
  if (!auth.user)
    return (
      <ScreenState
        loading={!auth.userError}
        title={
          auth.userError ? 'Couldn’t load your account' : 'Loading your account'
        }
        onRetry={auth.userError ? auth.retryUser : undefined}
      />
    );
  return (
    <JobForm
      key={auth.user.id}
      onClose={() => router.dismissTo('/jobwizard')}
      onSaved={(job) =>
        router.replace({ pathname: '/jobwizard/[id]', params: { id: job.id } })
      }
    />
  );
}
